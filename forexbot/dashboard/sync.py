"""Sincronização entre broker, JSONL e base de dados Django."""
import logging
from datetime import datetime, timezone

from django.core.management import call_command
from django.utils import timezone as dj_timezone

from forexbot.core import decision_logger as dl
from forexbot.dashboard.models import Trade

log = logging.getLogger(__name__)


def import_decision_logs() -> int:
    """Importa logs JSONL para Trade e DecisionLog."""
    call_command("import_logs", verbosity=0)
    return Trade.objects.count()


def _infer_exit_reason(trade: Trade, close_price: float | None) -> str:
    if close_price is None:
        return "broker_close"
    if trade.sl and abs(close_price - trade.sl) < abs(close_price - trade.tp):
        return "SL"
    if trade.tp and abs(close_price - trade.tp) <= abs(close_price - trade.sl):
        return "TP"
    return "broker_close"


def _mark_legacy_closed(trade: Trade) -> None:
    """Fecha trade antigo/inexistente no broker sem PnL (ex: mudança de conta)."""
    now = dj_timezone.now()
    Trade.objects.filter(pk=trade.pk).update(
        closed_at=now,
        exit_reason="legacy_account",
        pnl=None,
        pips=None,
    )
    log.info(
        "Trade legado fechado na BD (sem PnL broker): ticket=%s %s",
        trade.ticket,
        trade.symbol,
    )


def sync_closed_trades(broker, notifier=None) -> int:
    """
    Marca trades fechados no broker como fechados na BD com PnL real.
    Retorna número de trades atualizados neste ciclo.
    """
    from forexbot.broker.ctrader_broker import (
        compute_close_pnl,
        pip_size_from_info,
    )

    open_broker = {p["ticket"] for p in broker.get_open_positions()}
    db_open = Trade.objects.filter(closed_at__isnull=True)
    updated = 0
    legacy = 0

    for trade in db_open:
        if trade.ticket in open_broker:
            continue

        try:
            position_id = int(trade.ticket)
        except ValueError:
            log.warning(
                "Ticket não numérico (não é positionId): %s — a marcar legado",
                trade.ticket,
            )
            _mark_legacy_closed(trade)
            legacy += 1
            continue

        from_ms = int(trade.opened_at.timestamp() * 1000)
        deals = broker.get_deals_by_position(position_id, from_ts_ms=from_ms)
        close_deal = None
        for deal in reversed(deals):
            if deal.HasField("closePositionDetail"):
                close_deal = deal
                break

        if close_deal is None:
            _mark_legacy_closed(trade)
            legacy += 1
            continue

        pnl_data = compute_close_pnl(close_deal, broker._client._money_digits)
        if pnl_data is None:
            _mark_legacy_closed(trade)
            legacy += 1
            continue

        net_pnl, close_price, closed_ts_ms = pnl_data
        closed_at = datetime.fromtimestamp(closed_ts_ms / 1000, tz=timezone.utc)
        if dj_timezone.is_naive(closed_at):
            closed_at = dj_timezone.make_aware(closed_at, timezone.utc)

        sym_info = broker._client.get_symbol_info(trade.symbol)
        pips = 0.0
        if sym_info and trade.entry:
            ps = pip_size_from_info(sym_info)
            if ps > 0 and close_price:
                price_move = close_price - trade.entry
                if trade.direction == "SHORT":
                    price_move = -price_move
                pips = round(price_move / ps, 1)

        exit_reason = _infer_exit_reason(trade, close_price)
        duration_min = int((closed_at - trade.opened_at).total_seconds() / 60)

        Trade.objects.filter(pk=trade.pk).update(
            closed_at=closed_at,
            pnl=round(net_pnl, 2),
            pips=pips,
            exit_reason=exit_reason,
        )
        dl.log_trade_close(
            ticket=trade.ticket,
            symbol=trade.symbol,
            strategy=trade.strategy,
            pnl=round(net_pnl, 2),
            pips=pips,
            duration_min=duration_min,
            exit_reason=exit_reason,
        )
        updated += 1
        log.info(
            "Trade fechado sync: ticket=%s %s pnl=%.2f (%s)",
            trade.ticket,
            trade.symbol,
            net_pnl,
            exit_reason,
        )

    if updated or legacy:
        log.info(
            "Sincronização DB: %d trades fechados com PnL, %d legados arquivados",
            updated,
            legacy,
        )
    if updated and notifier:
        notifier.send_warning(
            "Sync DB",
            f"{updated} trade(s) fechado(s), {legacy} legado(s) arquivado(s)",
        )

    return updated

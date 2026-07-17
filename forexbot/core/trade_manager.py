"""Gestão de posições abertas — trailing SL em degraus."""
from __future__ import annotations

import logging

from forexbot import config

log = logging.getLogger(__name__)

# (progresso até ao TP, fração do TP a proteger no SL)
# Avaliado do mais alto para o mais baixo.
DEFAULT_TRAIL_STEPS = (
    (0.70, 0.40),  # a 70% do TP → SL a 40% do TP
    (0.50, 0.10),  # a 50% do TP → SL a 10% do TP
)


def _last_price(client, symbol: str) -> float | None:
    """Preço recente via última vela M1 (fallback M15)."""
    for tf in ("M1", "M15"):
        try:
            bars = client.get_candles(symbol, tf, count=1)
            if not bars:
                continue
            bar = bars[-1]
            low = bar.low / 100000
            return low + bar.deltaClose / 100000
        except Exception:
            continue
    return None


def _desired_sl(
    direction: str,
    entry: float,
    tp: float,
    price: float,
    steps: tuple[tuple[float, float], ...] = DEFAULT_TRAIL_STEPS,
) -> tuple[float | None, float, float]:
    """
    Calcula novo SL com base no progresso até ao TP.
    Retorna (new_sl | None, progress 0-1, tp_distance).
    """
    if direction == "LONG":
        tp_dist = tp - entry
        if tp_dist <= 0:
            return None, 0.0, 0.0
        progress = (price - entry) / tp_dist
        for trigger, lock in steps:
            if progress + 1e-6 >= trigger:
                return entry + lock * tp_dist, progress, tp_dist
        return None, progress, tp_dist

    # SHORT
    tp_dist = entry - tp
    if tp_dist <= 0:
        return None, 0.0, 0.0
    progress = (entry - price) / tp_dist
    for trigger, lock in steps:
        if progress + 1e-6 >= trigger:
            return entry - lock * tp_dist, progress, tp_dist
    return None, progress, tp_dist


def _sl_is_improvement(direction: str, current_sl: float, new_sl: float, eps: float) -> bool:
    """Só move SL a favor (nunca alarga o risco)."""
    if current_sl <= 0:
        return True
    if direction == "LONG":
        return new_sl > current_sl + eps
    return new_sl < current_sl - eps


def manage_trailing_stops(broker, client, notifier=None) -> int:
    """
    Percorre posições abertas e sobe o SL em degraus:
      ≥50% do TP → SL a 10% do TP
      ≥70% do TP → SL a 40% do TP
    Retorna quantos SL foram alterados.
    """
    if not config.TRAIL_SL_ENABLED:
        return 0

    positions = broker.get_open_positions()
    if not positions:
        return 0

    updated = 0
    for pos in positions:
        symbol = pos.get("symbol") or ""
        ticket = pos.get("ticket") or ""
        direction = pos.get("direction") or ""
        entry = float(pos.get("entry") or 0)
        sl = float(pos.get("sl") or 0)
        tp = float(pos.get("tp") or 0)

        if not symbol or not ticket or entry <= 0 or tp <= 0:
            continue
        if direction not in ("LONG", "SHORT"):
            continue

        price = _last_price(client, symbol)
        if price is None or price <= 0:
            log.debug("Trail: sem preço para %s ticket=%s", symbol, ticket)
            continue

        new_sl, progress, tp_dist = _desired_sl(direction, entry, tp, price)
        if new_sl is None:
            continue

        digits = 5
        sym_info = client.get_symbol_info(symbol)
        if sym_info is not None:
            digits = sym_info.digits
        eps = 10 ** (-digits) / 2

        if not _sl_is_improvement(direction, sl, new_sl, eps):
            continue

        new_sl = round(new_sl, digits)
        ok = broker.amend_position_sltp(ticket, symbol, new_sl, tp)
        if ok:
            updated += 1
            log.info(
                "Trail SL %s %s ticket=%s: progress=%.0f%% → SL %.5f → %.5f "
                "(TP dist=%.5f)",
                symbol,
                direction,
                ticket,
                progress * 100,
                sl,
                new_sl,
                tp_dist,
            )

    return updated

"""
Loop principal do bot.
A cada fecho de vela M15, para cada par e estratégia ativa:
  1. Obter velas
  2. Avaliar estratégia
  3. Se sinal → calcular lote → abrir ordem
"""
import logging
import time
import traceback
from datetime import datetime, timedelta, timezone

from forexbot import config
from forexbot.broker.ctrader_broker import CTraderBroker, TradingCTraderClient
from forexbot.core import decision_logger as dl
from forexbot.core import risk_manager
from forexbot.core.candle import Candle
from forexbot.notifications.telegram import get_notifier
from forexbot.strategies.strategy_a.strategy import StrategyA
from forexbot.strategies.strategy_b.strategy import StrategyB
from forexbot.strategies.strategy_c.strategy import StrategyC

log = logging.getLogger(__name__)


def _sync_dashboard(broker, notifier) -> None:
    """Importa logs JSONL e sincroniza trades fechados com a BD."""
    try:
        import os

        import django
        from django.apps import apps

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dashboard_project.settings")
        if not apps.ready:
            django.setup()

        from forexbot.dashboard.sync import import_decision_logs, sync_closed_trades

        import_decision_logs()
        updated = sync_closed_trades(broker, notifier)
        log.info("Sincronização DB: %d trades fechados atualizados", updated)
    except Exception:
        log.warning("Sync do dashboard falhou", exc_info=True)


def _usdjpy_rate(client: TradingCTraderClient) -> float | None:
    """Obtém taxa USDJPY para conversão de pares JPY."""
    try:
        bars = client.get_candles("USDJPY", "M15", count=1)
        if not bars:
            return None
        bar = bars[-1]
        low = bar.low / 100000
        return low + bar.deltaClose / 100000
    except Exception:
        return None


def bars_to_candles(bars: list) -> list[Candle]:
    """Converte barras cTrader (delta encoding) em objetos Candle."""
    candles = []
    for bar in bars:
        low = bar.low / 100000
        ts = datetime.fromtimestamp(bar.utcTimestampInMinutes * 60, tz=timezone.utc)
        candles.append(Candle(
            timestamp=ts,
            open=low + bar.deltaOpen / 100000,
            high=low + bar.deltaHigh / 100000,
            low=low,
            close=low + bar.deltaClose / 100000,
            volume=float(bar.volume),
        ))
    return candles


def next_m15_close() -> datetime:
    """Calcula o próximo fecho de vela M15 + 5s de margem (UTC)."""
    now = datetime.now(timezone.utc)
    minutes = (now.minute // 15 + 1) * 15
    if minutes >= 60:
        return now.replace(minute=0, second=5, microsecond=0) + timedelta(hours=1)
    return now.replace(minute=minutes, second=5, microsecond=0)


def _configure_logging() -> None:
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logging.getLogger().setLevel(level)


def _load_strategies() -> list:
    strategies = []
    if config.STRATEGY_A_ENABLED:
        strategies.append(StrategyA())
    if config.STRATEGY_B_ENABLED:
        strategies.append(StrategyB())
    if config.STRATEGY_C_ENABLED:
        strategies.append(StrategyC())
    return strategies


def connect_bot():
    """Liga ao cTrader e devolve (client, broker, strategies, notifier)."""
    notifier = get_notifier()
    client = TradingCTraderClient(config.CTRADER_ACCESS_TOKEN)

    try:
        client.start()
    except Exception as e:
        tb = traceback.format_exc()
        notifier.send_error(
            context="Ligação cTrader",
            error=e,
            details=tb.split("\n")[-3] if tb else "",
        )
        dl.log_error(
            context="Ligação cTrader",
            message=str(e),
            traceback_str=tb,
        )
        raise

    symbols_map = client.load_symbols()
    if not symbols_map:
        notifier.send_warning("Símbolos", "Nenhum símbolo carregado")
        dl.log_error(
            context="Símbolos",
            message="Nenhum símbolo carregado",
            level="WARNING",
        )

    client.load_trader_info()
    loaded = client.preload_symbol_specs(config.SYMBOLS)
    if loaded < len(config.SYMBOLS):
        notifier.send_warning(
            "Símbolos",
            f"Specs carregados para {loaded}/{len(config.SYMBOLS)} símbolos",
        )
    broker = CTraderBroker(client)
    strategies = _load_strategies()
    log.info(
        "Ligação pronta: %d símbolos | %d estratégias | DRY_RUN=%s",
        len(symbols_map),
        len(strategies),
        config.DRY_RUN,
    )
    return client, broker, strategies, notifier


def run_cycle(
    client: TradingCTraderClient,
    broker: CTraderBroker,
    strategies: list,
    notifier,
) -> None:
    """Executa um ciclo M15 completo (análise + ordens)."""
    cycle_start = datetime.now(timezone.utc)
    total_evals = len(config.SYMBOLS) * len(strategies)
    stats = {"signals": 0, "trades": 0, "errors": 0, "no_signal": 0, "skipped": 0}

    log.info("── Ciclo M15 %s UTC ──", cycle_start.strftime("%Y-%m-%d %H:%M"))
    log.info(
        "A analisar %d pares × %d estratégias = %d avaliações",
        len(config.SYMBOLS),
        len(strategies),
        total_evals,
    )

    equity = broker.get_equity()
    log.info("Equity da conta: $%.2f", equity)
    if equity == 0.0:
        notifier.send_warning("Equity", "Equity retornou 0 — usando fallback")
        dl.log_error(
            context="Equity",
            message="Equity retornou 0 — usando fallback",
            level="WARNING",
        )

    usdjpy = _usdjpy_rate(client)

    eval_n = 0
    for symbol in config.SYMBOLS:
        log.info("▸ Par %s", symbol)
        for strategy in strategies:
            eval_n += 1
            label = f"[{strategy.name}][{symbol}]"
            try:
                log.info("%s (%d/%d) A obter velas M15...", label, eval_n, total_evals)
                bars = client.get_candles(symbol, "M15", count=200)
                candles = bars_to_candles(bars)

                if not candles:
                    stats["skipped"] += 1
                    dl.log_no_signal(
                        strategy.name, symbol, "sem velas recebidas", {}
                    )
                    continue

                last = candles[-1]
                log.info(
                    "%s %d velas | última %s close=%.5f",
                    label,
                    len(candles),
                    last.timestamp.strftime("%H:%M"),
                    last.close,
                )

                signal = strategy.evaluate(symbol, candles)

                if signal is not None:
                    stats["signals"] += 1
                    sym_info = client.get_symbol_info(symbol)
                    if sym_info is None:
                        notifier.send_warning(
                            "Lot sizing",
                            f"{symbol}: specs do símbolo indisponíveis",
                        )
                        dl.log_no_signal(
                            strategy.name,
                            symbol,
                            "specs do símbolo indisponíveis",
                            {},
                        )
                        stats["no_signal"] += 1
                        continue

                    jpy_rate = usdjpy if symbol.endswith("JPY") else None
                    lot = risk_manager.lot_size(
                        equity,
                        signal.entry,
                        signal.sl,
                        sym_info,
                        usdjpy_rate=jpy_rate,
                    )
                    log.info(
                        "%s SINAL %s lot=%s RR=1:%.1f",
                        label,
                        signal.direction.value,
                        f"{lot:.2f}" if lot is not None else "REJEITADO",
                        signal.rr_ratio,
                    )
                    if lot is None or lot <= 0:
                        stats["no_signal"] += 1
                        notifier.send_warning(
                            "Lot sizing",
                            f"{symbol}: lote fora dos limites min/max/step",
                        )
                        dl.log_no_signal(
                            strategy.name,
                            symbol,
                            "lot inválido — min/max/step",
                            {"lot": lot},
                        )
                        continue

                    ticket = broker.open_trade(signal, lot)
                    if ticket:
                        stats["trades"] += 1
                        dl.log_trade_open(signal, lot, ticket)
                        notifier.send_signal(signal, lot, ticket)
                        log.info("%s TRADE ABERTO ticket=%s", label, ticket)
                    else:
                        log.warning("%s Sinal ignorado — ordem não executada", label)
                else:
                    stats["no_signal"] += 1

            except Exception as e:
                stats["errors"] += 1
                log.error(
                    "%s erro: %s",
                    label,
                    e,
                    exc_info=True,
                )
                tb = traceback.format_exc()
                notifier.send_error(
                    context=f"Estratégia {strategy.name} · {symbol}",
                    error=e,
                    details=tb.split("\n")[-3] if tb else "",
                )
                dl.log_error(
                    context=f"Estratégia {strategy.name} · {symbol}",
                    message=str(e),
                    traceback_str=tb,
                )

    _sync_dashboard(broker, notifier)

    elapsed = (datetime.now(timezone.utc) - cycle_start).total_seconds()
    log.info(
        "── Ciclo concluído em %.0fs | sinais=%d trades=%d "
        "sem_sinal=%d sem_velas=%d erros=%d ──",
        elapsed,
        stats["signals"],
        stats["trades"],
        stats["no_signal"],
        stats["skipped"],
        stats["errors"],
    )


def run() -> None:
    """Ponto de entrada do loop principal."""
    _configure_logging()
    log.info("ForexBot v2 a iniciar...")

    client, broker, strategies, notifier = connect_bot()

    notifier.send(
        f"✅ <b>ForexBot v2 ligado</b>\n"
        f"Pares: {len(config.SYMBOLS)}\n"
        f"Estratégias: {[s.name for s in strategies]}\n"
        f"DRY_RUN: {config.DRY_RUN}"
    )

    log.info("Estratégias ativas: %s", [s.name for s in strategies])
    log.info("Pares: %s", config.SYMBOLS)

    while True:
        target = next_m15_close()
        wait = (target - datetime.now(timezone.utc)).total_seconds()
        if wait > 0:
            log.info(
                "À espera do próximo M15 — %ds até %s UTC",
                int(wait),
                target.strftime("%Y-%m-%d %H:%M"),
            )
            time.sleep(wait)

        run_cycle(client, broker, strategies, notifier)

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


def run() -> None:
    """Ponto de entrada do loop principal."""
    _configure_logging()
    log.info("ForexBot v2 a iniciar...")

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

    broker = CTraderBroker(client)
    strategies = _load_strategies()

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
            log.debug("Próximo ciclo em %.0fs (%s UTC)", wait, target.strftime("%H:%M"))
            time.sleep(wait)

        cycle_start = datetime.now(timezone.utc)
        log.info("── Ciclo M15 %s UTC ──", cycle_start.strftime("%Y-%m-%d %H:%M"))

        equity = broker.get_equity()
        if equity == 0.0:
            notifier.send_warning("Equity", "Equity retornou 0 — usando fallback")
            dl.log_error(
                context="Equity",
                message="Equity retornou 0 — usando fallback",
                level="WARNING",
            )

        for symbol in config.SYMBOLS:
            for strategy in strategies:
                try:
                    bars = client.get_candles(symbol, "M15", count=200)
                    candles = bars_to_candles(bars)

                    if not candles:
                        dl.log_no_signal(
                            strategy.name, symbol, "sem velas recebidas", {}
                        )
                        continue

                    signal = strategy.evaluate(symbol, candles)

                    if signal is not None:
                        lot = risk_manager.lot_size(
                            equity, signal.entry, signal.sl, symbol
                        )
                        if lot <= 0:
                            dl.log_no_signal(
                                strategy.name,
                                symbol,
                                "lot_size=0 — SL inválido",
                                {"lot": lot},
                            )
                            continue

                        ticket = broker.open_trade(signal, lot)
                        if ticket:
                            dl.log_trade_open(signal, lot, ticket)
                            notifier.send_signal(signal, lot, ticket)

                except Exception as e:
                    log.error(
                        "[%s][%s] erro: %s",
                        strategy.name,
                        symbol,
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

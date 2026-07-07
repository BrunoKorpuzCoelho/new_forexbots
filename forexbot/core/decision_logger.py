"""
Regista cada decisão do bot em ficheiro JSONL por dia.
Por cada ciclo M15 e par, grava indicadores, resultado e motivo.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from forexbot.core.signal import TradeSignal

log = logging.getLogger(__name__)

LOGS_DIR = Path("logs/decisions")
LOGS_DIR.mkdir(parents=True, exist_ok=True)

ERRORS_DIR = Path("logs/errors")
ERRORS_DIR.mkdir(parents=True, exist_ok=True)


def _log_file(date: datetime) -> Path:
    return LOGS_DIR / f"{date.strftime('%Y-%m-%d')}.jsonl"


def _error_log_file(date: datetime) -> Path:
    return ERRORS_DIR / f"{date.strftime('%Y-%m-%d')}.jsonl"


def _write(record: dict, ts: datetime) -> None:
    try:
        with open(_log_file(ts), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        log.error("Erro ao escrever log: %s", e)


def _write_error(record: dict, ts: datetime) -> None:
    try:
        with open(_error_log_file(ts), "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        log.error("Erro ao escrever log de erro: %s", e)


def log_error(
    context: str,
    message: str,
    traceback_str: str = "",
    level: str = "ERROR",
) -> None:
    """Grava erro no JSONL e tenta persistir na DB Django."""
    ts = datetime.now(timezone.utc)
    record = {
        "ts": ts.isoformat(),
        "result": level,
        "context": context,
        "message": message,
        "traceback": traceback_str,
    }
    _write_error(record, ts)

    try:
        from django.conf import settings

        if settings.configured:
            from forexbot.dashboard.models import ErrorLog

            ErrorLog.objects.create(
                level=level,
                context=context,
                message=message,
                traceback=traceback_str,
            )
    except Exception:
        pass


def log_no_signal(
    strategy: str,
    symbol: str,
    reason: str,
    indicators: dict,
    timestamp: datetime | None = None,
) -> None:
    """Regista um ciclo onde não houve sinal."""
    ts = timestamp or datetime.now(timezone.utc)
    record = {
        "ts": ts.isoformat(),
        "strategy": strategy,
        "symbol": symbol,
        "result": "NO_SIGNAL",
        "reason": reason,
        "indicators": indicators,
    }
    _write(record, ts)
    log.info("[%s][%s] NO_SIGNAL — %s", strategy, symbol, reason)


def log_signal(signal: TradeSignal, indicators: dict) -> None:
    """Regista um ciclo onde houve sinal de entrada."""
    record = {
        "ts": signal.timestamp.isoformat(),
        "strategy": signal.strategy,
        "symbol": signal.symbol,
        "result": "SIGNAL",
        "direction": signal.direction.value,
        "entry": signal.entry,
        "sl": signal.sl,
        "tp": signal.tp,
        "rr": signal.rr_ratio,
        "reason": signal.reason,
        "indicators": indicators,
    }
    _write(record, signal.timestamp)
    log.info(
        "[%s][%s] SIGNAL %s E=%s SL=%s TP=%s | %s",
        signal.strategy,
        signal.symbol,
        signal.direction.value,
        signal.entry,
        signal.sl,
        signal.tp,
        signal.reason,
    )


def log_trade_open(signal: TradeSignal, lot: float, ticket: str) -> None:
    """Regista abertura de trade."""
    record = {
        "ts": signal.timestamp.isoformat(),
        "strategy": signal.strategy,
        "symbol": signal.symbol,
        "result": "TRADE_OPEN",
        "ticket": ticket,
        "direction": signal.direction.value,
        "entry": signal.entry,
        "sl": signal.sl,
        "tp": signal.tp,
        "lot": lot,
        "reason": signal.reason,
    }
    _write(record, signal.timestamp)
    log.info(
        "[%s][%s] TRADE_OPEN ticket=%s lot=%s",
        signal.strategy,
        signal.symbol,
        ticket,
        lot,
    )


def log_trade_close(
    ticket: str,
    symbol: str,
    strategy: str,
    pnl: float,
    pips: float,
    duration_min: int,
    exit_reason: str,
) -> None:
    """Regista fecho de trade."""
    ts = datetime.now(timezone.utc)
    record = {
        "ts": ts.isoformat(),
        "strategy": strategy,
        "symbol": symbol,
        "result": "TRADE_CLOSE",
        "ticket": ticket,
        "pnl": pnl,
        "pips": pips,
        "duration_min": duration_min,
        "exit_reason": exit_reason,
    }
    _write(record, ts)
    log.info(
        "[%s][%s] TRADE_CLOSE ticket=%s pnl=%s pips=%s",
        strategy,
        symbol,
        ticket,
        pnl,
        pips,
    )

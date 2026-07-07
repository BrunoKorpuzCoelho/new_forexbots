"""Cálculo de tamanho de lote baseado em risco percentual."""
import logging

from forexbot import config

log = logging.getLogger(__name__)

PIP_VALUE_PER_LOT: dict[str, float] = {
    "XAUUSD": 10.0,
    "XAGUSD": 50.0,
    "XTIUSD": 10.0,
    "BTCUSD": 1.0,
    "ETHUSD": 1.0,
    "SOLUSD": 1.0,
    "XRPUSD": 1.0,
    "default": 10.0,
}

MIN_LOT = 0.01
MAX_LOT = 2.0


def pip_multiplier(symbol: str) -> float:
    """Converte diferença de preço em pips."""
    if symbol.endswith("JPY"):
        return 100.0
    if symbol in ("XAUUSD", "XAGUSD"):
        return 10.0
    if symbol in ("BTCUSD", "ETHUSD"):
        return 1.0
    if symbol in ("XRPUSD", "SOLUSD"):
        return 1000.0
    if symbol == "XTIUSD":
        return 100.0
    return 10000.0


def pip_value(symbol: str) -> float:
    """Valor USD por pip por lote standard."""
    return PIP_VALUE_PER_LOT.get(symbol, PIP_VALUE_PER_LOT["default"])


def lot_size(equity: float, entry: float, sl: float, symbol: str) -> float:
    """
    Calcula lote baseado em equity, RISK_PCT e distância ao SL.
    Retorna MIN_LOT se SL demasiado pequeno.
    """
    risk_amount = equity * (config.RISK_PCT / 100)
    sl_pips = abs(entry - sl) * pip_multiplier(symbol)

    if sl_pips < 0.1:
        log.warning(
            "SL demasiado pequeno (%.2f pips) para %s — a usar lote mínimo",
            sl_pips,
            symbol,
        )
        return MIN_LOT

    lot = risk_amount / (sl_pips * pip_value(symbol))
    lot = round(max(MIN_LOT, min(MAX_LOT, lot)), 2)
    log.debug(
        "lot_size: equity=%.2f risk=%.2f sl_pips=%.1f lot=%.2f",
        equity,
        risk_amount,
        sl_pips,
        lot,
    )
    return lot

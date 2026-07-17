"""
Estratégia B — Bollinger Bands + RSI (Mean Reversion).

LONG:  close <= BB lower(20,2) + RSI(14) < 35
SHORT: close >= BB upper(20,2) + RSI(14) > 65

SL = 1×ATR a partir da entrada.
TP = mesma distância do SL (risco/recompensa 1:1).

STRATEGY_B_INVERT=true inverte a direção (LONG↔SHORT) sem mudar as condições.
"""
import logging

import pandas as pd
import pandas_ta as ta

from forexbot import config
from forexbot.core import decision_logger as dl
from forexbot.core.candle import Candle
from forexbot.core.signal import Direction, TradeSignal
from forexbot.strategies.base import BaseStrategy

log = logging.getLogger(__name__)

RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65


def _bb_column_names(bb: pd.DataFrame) -> tuple[str, str, str] | None:
    """Resolve nomes das bandas (variam entre versões do pandas-ta)."""
    try:
        lower = next(c for c in bb.columns if c.startswith("BBL_"))
        middle = next(c for c in bb.columns if c.startswith("BBM_"))
        upper = next(c for c in bb.columns if c.startswith("BBU_"))
        return lower, middle, upper
    except StopIteration:
        return None


def _sl_tp_1_to_1(entry: float, direction: Direction, risk: float) -> tuple[float, float]:
    """SL e TP à mesma distância (1:1), com risco baseado no ATR."""
    if direction == Direction.LONG:
        return entry - risk, entry + risk
    return entry + risk, entry - risk


class StrategyB(BaseStrategy):

    @property
    def name(self) -> str:
        return "B"

    def evaluate(self, symbol: str, candles: list[Candle]) -> TradeSignal | None:
        if len(candles) < 30:
            dl.log_no_signal("B", symbol, "candles insuficientes", {"count": len(candles)})
            return None

        df = pd.DataFrame([{
            "high": c.high,
            "low": c.low,
            "close": c.close,
        } for c in candles])

        bb = ta.bbands(df["close"], length=20, std=2)
        rsi = ta.rsi(df["close"], length=14)
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)

        if bb is None or rsi is None or atr is None:
            dl.log_no_signal("B", symbol, "indicadores não calculados", {})
            return None

        bb_cols = _bb_column_names(bb)
        if bb_cols is None:
            dl.log_no_signal("B", symbol, "colunas BB não encontradas", {"cols": list(bb.columns)})
            return None

        lower_col, middle_col, upper_col = bb_cols
        df = pd.concat([df, bb, rsi.rename("rsi"), atr.rename("atr")], axis=1)
        curr = df.iloc[-2]
        last_candle = candles[-2]

        lower = curr[lower_col]
        middle = curr[middle_col]
        upper = curr[upper_col]
        close = curr["close"]
        rsi_v = curr["rsi"]
        atr_v = curr["atr"]

        indicators = {
            "close": round(close, 5),
            "bb_low": round(lower, 5),
            "bb_mid": round(middle, 5),
            "bb_up": round(upper, 5),
            "rsi": round(rsi_v, 2),
            "atr": round(atr_v, 5),
            "rr": "1:1",
            "invert": config.STRATEGY_B_INVERT,
        }

        direction: Direction | None = None
        reason = ""

        if close <= lower and rsi_v < RSI_OVERSOLD:
            direction = Direction.LONG
            reason = f"Preço ({close:.5f}) ≤ BB lower ({lower:.5f}) · RSI={rsi_v:.1f}"
        elif close >= upper and rsi_v > RSI_OVERBOUGHT:
            direction = Direction.SHORT
            reason = f"Preço ({close:.5f}) ≥ BB upper ({upper:.5f}) · RSI={rsi_v:.1f}"

        if direction is None:
            if close <= lower:
                reason = f"Preço na BB lower mas RSI={rsi_v:.1f} ≥ {RSI_OVERSOLD} (sem confirmação)"
            elif close >= upper:
                reason = f"Preço na BB upper mas RSI={rsi_v:.1f} ≤ {RSI_OVERBOUGHT} (sem confirmação)"
            else:
                reason = f"Preço ({close:.5f}) dentro das bandas [{lower:.5f}, {upper:.5f}]"
            dl.log_no_signal("B", symbol, reason, indicators)
            return None

        if config.STRATEGY_B_INVERT:
            direction = (
                Direction.SHORT if direction == Direction.LONG else Direction.LONG
            )
            reason = f"[INVERT] {reason}"

        entry = last_candle.close
        sl, tp = _sl_tp_1_to_1(entry, direction, atr_v)
        signal = TradeSignal(
            "B", symbol, direction, entry, sl, tp, reason, last_candle.timestamp
        )
        dl.log_signal(signal, indicators)
        return signal

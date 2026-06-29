"""
Estratégia B — Bollinger Bands + RSI (Mean Reversion).

LONG:  close <= BB lower(20,2) + RSI(14) < 35
SHORT: close >= BB upper(20,2) + RSI(14) > 65
"""
import logging

import pandas as pd
import pandas_ta as ta

from forexbot.core import decision_logger as dl
from forexbot.core.candle import Candle
from forexbot.core.signal import Direction, TradeSignal
from forexbot.strategies.base import BaseStrategy

log = logging.getLogger(__name__)

RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65


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

        df = pd.concat([df, bb, rsi.rename("rsi"), atr.rename("atr")], axis=1)
        curr = df.iloc[-2]
        last_candle = candles[-2]

        lower = curr["BBL_20_2.0"]
        middle = curr["BBM_20_2.0"]
        upper = curr["BBU_20_2.0"]
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
        }

        if close <= lower and rsi_v < RSI_OVERSOLD:
            entry = last_candle.close
            sl = entry - atr_v
            tp = middle
            reason = f"Preço ({close:.5f}) ≤ BB lower ({lower:.5f}) · RSI={rsi_v:.1f}"
            signal = TradeSignal(
                "B", symbol, Direction.LONG, entry, sl, tp, reason, last_candle.timestamp
            )
            dl.log_signal(signal, indicators)
            return signal

        if close >= upper and rsi_v > RSI_OVERBOUGHT:
            entry = last_candle.close
            sl = entry + atr_v
            tp = middle
            reason = f"Preço ({close:.5f}) ≥ BB upper ({upper:.5f}) · RSI={rsi_v:.1f}"
            signal = TradeSignal(
                "B", symbol, Direction.SHORT, entry, sl, tp, reason, last_candle.timestamp
            )
            dl.log_signal(signal, indicators)
            return signal

        if close <= lower:
            reason = f"Preço na BB lower mas RSI={rsi_v:.1f} ≥ {RSI_OVERSOLD} (sem confirmação)"
        elif close >= upper:
            reason = f"Preço na BB upper mas RSI={rsi_v:.1f} ≤ {RSI_OVERBOUGHT} (sem confirmação)"
        else:
            reason = f"Preço ({close:.5f}) dentro das bandas [{lower:.5f}, {upper:.5f}]"

        dl.log_no_signal("B", symbol, reason, indicators)
        return None

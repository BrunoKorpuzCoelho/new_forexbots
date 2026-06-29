"""
Estratégia A — EMA Crossover + RSI (Trend Following).

LONG:  EMA9 cruza EMA21 para cima  + RSI(14) > 50
SHORT: EMA9 cruza EMA21 para baixo + RSI(14) < 50
"""
import logging

import pandas as pd
import pandas_ta as ta

from forexbot.core import decision_logger as dl
from forexbot.core.candle import Candle
from forexbot.core.signal import Direction, TradeSignal
from forexbot.strategies.base import BaseStrategy

log = logging.getLogger(__name__)


def _pip_buffer(symbol: str) -> float:
    if symbol in ("XAUUSD", "XAGUSD"):
        return 0.20
    if symbol in ("BTCUSD", "ETHUSD"):
        return 2.0
    if symbol in ("XRPUSD", "SOLUSD"):
        return 0.002
    return 0.0002


class StrategyA(BaseStrategy):

    @property
    def name(self) -> str:
        return "A"

    def evaluate(self, symbol: str, candles: list[Candle]) -> TradeSignal | None:
        if len(candles) < 30:
            dl.log_no_signal("A", symbol, "candles insuficientes", {"count": len(candles)})
            return None

        df = pd.DataFrame([{
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
        } for c in candles])

        df["ema9"] = ta.ema(df["close"], length=9)
        df["ema21"] = ta.ema(df["close"], length=21)
        df["rsi"] = ta.rsi(df["close"], length=14)

        prev = df.iloc[-3]
        curr = df.iloc[-2]
        last_candle = candles[-2]

        ema9_curr = curr["ema9"]
        ema21_curr = curr["ema21"]
        ema9_prev = prev["ema9"]
        ema21_prev = prev["ema21"]
        rsi = curr["rsi"]

        indicators = {
            "ema9": round(ema9_curr, 5),
            "ema21": round(ema21_curr, 5),
            "rsi": round(rsi, 2),
            "cross": (
                "up" if ema9_curr > ema21_curr and ema9_prev <= ema21_prev
                else "down" if ema9_curr < ema21_curr and ema9_prev >= ema21_prev
                else "none"
            ),
        }

        crossed_up = ema9_prev <= ema21_prev and ema9_curr > ema21_curr
        crossed_down = ema9_prev >= ema21_prev and ema9_curr < ema21_curr
        buffer = _pip_buffer(symbol)

        if crossed_up and rsi > 50:
            swing_low = min(c.low for c in candles[-7:-2])
            entry = last_candle.close
            sl = swing_low - buffer
            tp = entry + 2 * (entry - sl)
            reason = f"EMA9 cruzou EMA21 ↑ · RSI={rsi:.1f}"
            signal = TradeSignal(
                "A", symbol, Direction.LONG, entry, sl, tp, reason, last_candle.timestamp
            )
            dl.log_signal(signal, indicators)
            return signal

        if crossed_down and rsi < 50:
            swing_high = max(c.high for c in candles[-7:-2])
            entry = last_candle.close
            sl = swing_high + buffer
            tp = entry - 2 * (sl - entry)
            reason = f"EMA9 cruzou EMA21 ↓ · RSI={rsi:.1f}"
            signal = TradeSignal(
                "A", symbol, Direction.SHORT, entry, sl, tp, reason, last_candle.timestamp
            )
            dl.log_signal(signal, indicators)
            return signal

        if crossed_up and rsi <= 50:
            reason = f"Cruzamento ↑ mas RSI={rsi:.1f} ≤ 50 (sem confirmação)"
        elif crossed_down and rsi >= 50:
            reason = f"Cruzamento ↓ mas RSI={rsi:.1f} ≥ 50 (sem confirmação)"
        else:
            reason = f"Sem cruzamento EMA · EMA9={ema9_curr:.5f} EMA21={ema21_curr:.5f}"

        dl.log_no_signal("A", symbol, reason, indicators)
        return None

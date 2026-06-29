"""
Estratégia C — Opening Range Breakout (ORB).

Range: primeiros 30 min da sessão London (07:00–07:30 UTC).
Avalia apenas entre 07:30 e 10:00 UTC.

LONG:  close > range_high + close > EMA50
SHORT: close < range_low  + close < EMA50
"""
import logging
from datetime import datetime, timezone

import pandas as pd
import pandas_ta as ta

from forexbot.core import decision_logger as dl
from forexbot.core.candle import Candle
from forexbot.core.signal import Direction, TradeSignal
from forexbot.strategies.base import BaseStrategy

log = logging.getLogger(__name__)


def _in_orb_window(ts: datetime) -> bool:
    ts = ts.astimezone(timezone.utc)
    if ts.hour < 7 or ts.hour >= 10:
        return False
    if ts.hour == 7 and ts.minute < 30:
        return False
    return True


class StrategyC(BaseStrategy):

    @property
    def name(self) -> str:
        return "C"

    def evaluate(self, symbol: str, candles: list[Candle]) -> TradeSignal | None:
        if len(candles) < 60:
            dl.log_no_signal("C", symbol, "candles insuficientes", {"count": len(candles)})
            return None

        last_candle = candles[-2]
        ts = last_candle.timestamp.astimezone(timezone.utc)

        if not _in_orb_window(ts):
            dl.log_no_signal(
                "C", symbol, f"fora da janela ORB (hora UTC={ts.hour}:{ts.minute:02d})",
                {"hour": ts.hour, "minute": ts.minute},
            )
            return None

        range_candles = [
            c for c in candles
            if c.timestamp.astimezone(timezone.utc).hour == 7
            and c.timestamp.astimezone(timezone.utc).minute < 30
        ]

        if len(range_candles) < 2:
            dl.log_no_signal(
                "C", symbol, "range insuficiente",
                {"range_count": len(range_candles)},
            )
            return None

        range_high = max(c.high for c in range_candles)
        range_low = min(c.low for c in range_candles)

        df = pd.DataFrame([{
            "close": c.close,
            "high": c.high,
            "low": c.low,
        } for c in candles])
        df["ema50"] = ta.ema(df["close"], length=50)
        df["atr"] = ta.atr(df["high"], df["low"], df["close"], length=14)
        curr = df.iloc[-2]

        ema50 = curr["ema50"]
        atr = curr["atr"]
        close = last_candle.close

        indicators = {
            "range_high": round(range_high, 5),
            "range_low": round(range_low, 5),
            "close": round(close, 5),
            "ema50": round(ema50, 5),
            "atr": round(atr, 5),
        }

        if close > range_high and close > ema50:
            entry = close
            sl = entry - (1.5 * atr)
            tp = entry + 2 * (entry - sl)
            reason = (
                f"ORB breakout ↑ | close={close:.5f} > range_high={range_high:.5f} "
                f"· EMA50={ema50:.5f} (tendência ↑)"
            )
            signal = TradeSignal(
                "C", symbol, Direction.LONG, entry, sl, tp, reason, last_candle.timestamp
            )
            dl.log_signal(signal, indicators)
            return signal

        if close < range_low and close < ema50:
            entry = close
            sl = entry + (1.5 * atr)
            tp = entry - 2 * (sl - entry)
            reason = (
                f"ORB breakout ↓ | close={close:.5f} < range_low={range_low:.5f} "
                f"· EMA50={ema50:.5f} (tendência ↓)"
            )
            signal = TradeSignal(
                "C", symbol, Direction.SHORT, entry, sl, tp, reason, last_candle.timestamp
            )
            dl.log_signal(signal, indicators)
            return signal

        if close > range_high:
            reason = f"Breakout ↑ mas close={close:.5f} < EMA50={ema50:.5f} (tendência não confirma)"
        elif close < range_low:
            reason = f"Breakout ↓ mas close={close:.5f} > EMA50={ema50:.5f} (tendência não confirma)"
        else:
            reason = f"Sem breakout | close={close:.5f} dentro de [{range_low:.5f}, {range_high:.5f}]"

        dl.log_no_signal("C", symbol, reason, indicators)
        return None

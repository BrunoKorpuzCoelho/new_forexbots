"""Modelo de vela OHLCV."""
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    def __repr__(self) -> str:
        d = self.timestamp.strftime("%Y-%m-%d %H:%M")
        return (
            f"Candle({d} O={self.open:.5f} H={self.high:.5f} "
            f"L={self.low:.5f} C={self.close:.5f})"
        )

"""Modelo de sinal de trade."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class Direction(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class TradeSignal:
    strategy: str
    symbol: str
    direction: Direction
    entry: float
    sl: float
    tp: float
    reason: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    @property
    def risk_pips(self) -> float:
        return abs(self.entry - self.sl)

    @property
    def reward_pips(self) -> float:
        return abs(self.tp - self.entry)

    @property
    def rr_ratio(self) -> float:
        if self.risk_pips == 0:
            return 0.0
        return round(self.reward_pips / self.risk_pips, 2)

    def __repr__(self) -> str:
        return (
            f"Signal({self.strategy} {self.symbol} {self.direction.value} "
            f"E={self.entry} SL={self.sl} TP={self.tp} RR={self.rr_ratio})"
        )

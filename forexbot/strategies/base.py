"""Interface base para todas as estratégias."""
from abc import ABC, abstractmethod

from forexbot.core.candle import Candle
from forexbot.core.signal import TradeSignal


class BaseStrategy(ABC):
    """Interface que todas as estratégias têm de implementar."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome da estratégia: 'A', 'B', 'C'."""

    @abstractmethod
    def evaluate(self, symbol: str, candles: list[Candle]) -> TradeSignal | None:
        """
        Avalia as velas e retorna um sinal ou None.
        Deve chamar decision_logger.log_no_signal() quando não há sinal.
        Deve chamar decision_logger.log_signal() quando há sinal.
        Nunca retornar None em silêncio.
        """

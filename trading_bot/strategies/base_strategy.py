"""
Base strategy interface and signal definitions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


class SignalType(Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


@dataclass
class Signal:
    """A trading signal from a strategy."""
    signal_type: SignalType
    confidence: float          # 0.0 to 1.0
    strategy_name: str
    details: dict = field(default_factory=dict)

    @property
    def direction(self) -> int:
        """Returns +1 for buy, -1 for sell, 0 for neutral."""
        if self.signal_type in (SignalType.BUY, SignalType.STRONG_BUY):
            return 1
        elif self.signal_type in (SignalType.SELL, SignalType.STRONG_SELL):
            return -1
        return 0


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""

    name: str = "base"
    weight: float = 0.25  # Default weight in composite scoring

    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> Signal:
        """Analyze a DataFrame with indicators and return a Signal."""
        ...

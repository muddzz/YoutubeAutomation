"""
Momentum strategy for crude oil futures.
Measures rate of change and acceleration of price movement
to ride strong momentum moves.
"""

import numpy as np
import pandas as pd

from trading_bot.strategies.base_strategy import BaseStrategy, Signal, SignalType


class MomentumStrategy(BaseStrategy):
    """Momentum-based strategy using ROC, MFI, and price acceleration."""

    name = "momentum"
    weight = 0.25

    def analyze(self, df: pd.DataFrame) -> Signal:
        if df.empty or len(df) < 30:
            return Signal(SignalType.NEUTRAL, 0.0, self.name, {})

        scores = []
        details = {}

        # 1. Rate of Change (ROC)
        roc_score = self._roc_signal(df)
        scores.append(("roc", roc_score, 0.25))
        details["roc"] = roc_score

        # 2. Money Flow Index
        mfi_score = self._mfi_signal(df)
        scores.append(("mfi", mfi_score, 0.20))
        details["mfi"] = mfi_score

        # 3. Price Acceleration (2nd derivative)
        accel_score = self._acceleration_signal(df)
        scores.append(("acceleration", accel_score, 0.20))
        details["acceleration"] = accel_score

        # 4. Multi-period momentum consistency
        consistency_score = self._momentum_consistency(df)
        scores.append(("consistency", consistency_score, 0.20))
        details["consistency"] = consistency_score

        # 5. Breakout detection
        breakout_score = self._breakout_signal(df)
        scores.append(("breakout", breakout_score, 0.15))
        details["breakout"] = breakout_score

        composite = sum(score * weight for _, score, weight in scores)
        confidence = min(abs(composite), 1.0)

        if composite > 0.15:
            signal_type = SignalType.BUY
        elif composite < -0.15:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.NEUTRAL

        return Signal(signal_type, confidence, self.name, details)

    def _roc_signal(self, df: pd.DataFrame) -> float:
        if "ROC" not in df.columns:
            return 0.0
        roc = df["ROC"].iloc[-1]
        if pd.isna(roc):
            return 0.0
        # Normalize ROC to -1 to 1 range (5% move = strong)
        return np.clip(roc / 5.0, -1.0, 1.0)

    def _mfi_signal(self, df: pd.DataFrame) -> float:
        if "MFI" not in df.columns:
            return 0.0
        mfi = df["MFI"].iloc[-1]
        if pd.isna(mfi):
            return 0.0

        # Strong money flow = momentum confirmation
        if mfi > 80:
            return 0.8
        elif mfi > 60:
            return 0.3
        elif mfi < 20:
            return -0.8
        elif mfi < 40:
            return -0.3
        return 0.0

    def _acceleration_signal(self, df: pd.DataFrame) -> float:
        """Measure if momentum is accelerating or decelerating."""
        if len(df) < 10:
            return 0.0

        close = df["Close"]
        # First derivative: returns
        returns = close.pct_change()
        # Second derivative: change in returns
        acceleration = returns.diff()

        recent_accel = acceleration.iloc[-5:].mean()
        if pd.isna(recent_accel):
            return 0.0

        return np.clip(recent_accel * 100, -1.0, 1.0)

    def _momentum_consistency(self, df: pd.DataFrame) -> float:
        """Check if momentum is consistent across multiple lookback periods."""
        if len(df) < 60:
            return 0.0

        close = df["Close"]
        periods = [5, 10, 20, 40]
        directions = []

        for p in periods:
            if len(close) > p:
                ret = (close.iloc[-1] / close.iloc[-p]) - 1
                directions.append(1 if ret > 0 else -1)

        if not directions:
            return 0.0

        # All periods agree = strong momentum
        avg_direction = np.mean(directions)
        return avg_direction  # -1 to +1

    def _breakout_signal(self, df: pd.DataFrame) -> float:
        """Detect breakouts from Donchian channels."""
        if not all(c in df.columns for c in ["Donchian_Upper", "Donchian_Lower"]):
            return 0.0

        last = df.iloc[-1]
        close = last["Close"]
        upper = last["Donchian_Upper"]
        lower = last["Donchian_Lower"]

        if pd.isna(upper) or pd.isna(lower):
            return 0.0

        if close >= upper:
            return 1.0  # Breakout to upside
        elif close <= lower:
            return -1.0  # Breakout to downside
        return 0.0

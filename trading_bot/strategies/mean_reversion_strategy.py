"""
Mean-reversion strategy for crude oil futures.
Identifies overbought/oversold conditions and price extremes
that are likely to revert to the mean.
"""

import numpy as np
import pandas as pd

from trading_bot.strategies.base_strategy import BaseStrategy, Signal, SignalType


class MeanReversionStrategy(BaseStrategy):
    """Identifies mean-reversion opportunities using oscillators and bands."""

    name = "mean_reversion"
    weight = 0.25

    def analyze(self, df: pd.DataFrame) -> Signal:
        if df.empty or len(df) < 30:
            return Signal(SignalType.NEUTRAL, 0.0, self.name, {})

        scores = []
        details = {}

        # 1. RSI Overbought/Oversold
        rsi_score = self._rsi_signal(df)
        scores.append(("rsi", rsi_score, 0.25))
        details["rsi"] = rsi_score

        # 2. Bollinger Band Position
        bb_score = self._bollinger_signal(df)
        scores.append(("bollinger", bb_score, 0.25))
        details["bollinger"] = bb_score

        # 3. Stochastic Oscillator
        stoch_score = self._stochastic_signal(df)
        scores.append(("stochastic", stoch_score, 0.20))
        details["stochastic"] = stoch_score

        # 4. Williams %R
        williams_score = self._williams_signal(df)
        scores.append(("williams_r", williams_score, 0.15))
        details["williams_r"] = williams_score

        # 5. CCI
        cci_score = self._cci_signal(df)
        scores.append(("cci", cci_score, 0.15))
        details["cci"] = cci_score

        composite = sum(score * weight for _, score, weight in scores)
        confidence = min(abs(composite), 1.0)

        # Mean reversion signals are contrarian
        if composite > 0.15:
            signal_type = SignalType.BUY
        elif composite < -0.15:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.NEUTRAL

        return Signal(signal_type, confidence, self.name, details)

    def _rsi_signal(self, df: pd.DataFrame) -> float:
        if "RSI" not in df.columns:
            return 0.0
        rsi = df["RSI"].iloc[-1]
        if pd.isna(rsi):
            return 0.0

        # Extreme oversold = strong buy signal (mean reversion up)
        if rsi < 20:
            return 1.0
        elif rsi < 30:
            return 0.6
        elif rsi < 40:
            return 0.2
        # Extreme overbought = strong sell signal (mean reversion down)
        elif rsi > 80:
            return -1.0
        elif rsi > 70:
            return -0.6
        elif rsi > 60:
            return -0.2
        return 0.0

    def _bollinger_signal(self, df: pd.DataFrame) -> float:
        if "BB_Position" not in df.columns:
            return 0.0
        pos = df["BB_Position"].iloc[-1]
        if pd.isna(pos):
            return 0.0

        # Below lower band = oversold, expect reversion up
        if pos < 0:
            return min(abs(pos), 1.0)
        # Above upper band = overbought, expect reversion down
        elif pos > 1:
            return -min(pos - 1, 1.0)
        # Near middle = neutral
        elif 0.3 < pos < 0.7:
            return 0.0
        elif pos <= 0.3:
            return 0.3
        else:
            return -0.3

    def _stochastic_signal(self, df: pd.DataFrame) -> float:
        if "Stoch_K" not in df.columns or "Stoch_D" not in df.columns:
            return 0.0
        k = df["Stoch_K"].iloc[-1]
        d = df["Stoch_D"].iloc[-1]
        if pd.isna(k) or pd.isna(d):
            return 0.0

        score = 0.0
        # Oversold zone
        if k < 20 and d < 20:
            score = 0.7
            if k > d:  # Bullish crossover in oversold
                score = 1.0
        # Overbought zone
        elif k > 80 and d > 80:
            score = -0.7
            if k < d:  # Bearish crossover in overbought
                score = -1.0

        return score

    def _williams_signal(self, df: pd.DataFrame) -> float:
        if "Williams_R" not in df.columns:
            return 0.0
        wr = df["Williams_R"].iloc[-1]
        if pd.isna(wr):
            return 0.0

        if wr < -80:
            return 0.8  # Oversold
        elif wr > -20:
            return -0.8  # Overbought
        return 0.0

    def _cci_signal(self, df: pd.DataFrame) -> float:
        if "CCI" not in df.columns:
            return 0.0
        cci = df["CCI"].iloc[-1]
        if pd.isna(cci):
            return 0.0

        if cci < -200:
            return 1.0
        elif cci < -100:
            return 0.5
        elif cci > 200:
            return -1.0
        elif cci > 100:
            return -0.5
        return 0.0

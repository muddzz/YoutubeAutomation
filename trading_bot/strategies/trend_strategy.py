"""
Trend-following strategy for crude oil futures.
Uses moving average crossovers, MACD, ADX, Ichimoku, and Supertrend
to identify and follow strong trends.
"""

import numpy as np
import pandas as pd

from trading_bot.strategies.base_strategy import BaseStrategy, Signal, SignalType


class TrendStrategy(BaseStrategy):
    """Multi-indicator trend-following strategy."""

    name = "trend_following"
    weight = 0.30  # 30% of composite signal

    def analyze(self, df: pd.DataFrame) -> Signal:
        if df.empty or len(df) < 50:
            return Signal(SignalType.NEUTRAL, 0.0, self.name, {})

        scores = []
        details = {}

        # 1. Moving Average Alignment (Golden/Death Cross)
        ma_score = self._ma_alignment(df)
        scores.append(("ma_alignment", ma_score, 0.20))
        details["ma_alignment"] = ma_score

        # 2. MACD Signal
        macd_score = self._macd_signal(df)
        scores.append(("macd", macd_score, 0.20))
        details["macd"] = macd_score

        # 3. ADX Trend Strength
        adx_score = self._adx_signal(df)
        scores.append(("adx", adx_score, 0.15))
        details["adx"] = adx_score

        # 4. Ichimoku Cloud
        ichimoku_score = self._ichimoku_signal(df)
        scores.append(("ichimoku", ichimoku_score, 0.20))
        details["ichimoku"] = ichimoku_score

        # 5. Supertrend
        supertrend_score = self._supertrend_signal(df)
        scores.append(("supertrend", supertrend_score, 0.15))
        details["supertrend"] = supertrend_score

        # 6. Price vs VWAP
        vwap_score = self._vwap_signal(df)
        scores.append(("vwap", vwap_score, 0.10))
        details["vwap"] = vwap_score

        # Weighted composite
        composite = sum(score * weight for _, score, weight in scores)
        confidence = min(abs(composite), 1.0)

        if composite > 0.15:
            signal_type = SignalType.BUY
        elif composite < -0.15:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.NEUTRAL

        return Signal(signal_type, confidence, self.name, details)

    def _ma_alignment(self, df: pd.DataFrame) -> float:
        """Score based on moving average alignment. +1 = perfect bullish, -1 = bearish."""
        cols_needed = ["EMA_9", "EMA_21", "SMA_50", "SMA_200"]
        if not all(c in df.columns for c in cols_needed):
            return 0.0

        last = df.iloc[-1]
        score = 0.0

        # EMA 9 > EMA 21 (short-term trend)
        if last["EMA_9"] > last["EMA_21"]:
            score += 0.3
        else:
            score -= 0.3

        # EMA 21 > SMA 50 (medium-term)
        if last["EMA_21"] > last["SMA_50"]:
            score += 0.3
        else:
            score -= 0.3

        # SMA 50 > SMA 200 (long-term / golden cross)
        if last["SMA_50"] > last["SMA_200"]:
            score += 0.4
        else:
            score -= 0.4

        return np.clip(score, -1.0, 1.0)

    def _macd_signal(self, df: pd.DataFrame) -> float:
        if "MACD" not in df.columns or "MACD_Signal" not in df.columns:
            return 0.0
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last

        score = 0.0
        # MACD above signal line
        if last["MACD"] > last["MACD_Signal"]:
            score += 0.4
        else:
            score -= 0.4

        # MACD crossing signal (momentum shift)
        if prev["MACD"] <= prev["MACD_Signal"] and last["MACD"] > last["MACD_Signal"]:
            score += 0.3  # Bullish crossover
        elif prev["MACD"] >= prev["MACD_Signal"] and last["MACD"] < last["MACD_Signal"]:
            score -= 0.3  # Bearish crossover

        # Histogram direction
        if "MACD_Histogram" in df.columns:
            hist = df["MACD_Histogram"].iloc[-3:]
            if len(hist) == 3 and hist.iloc[-1] > hist.iloc[-2]:
                score += 0.3
            elif len(hist) == 3 and hist.iloc[-1] < hist.iloc[-2]:
                score -= 0.3

        return np.clip(score, -1.0, 1.0)

    def _adx_signal(self, df: pd.DataFrame) -> float:
        if not all(c in df.columns for c in ["ADX", "Plus_DI", "Minus_DI"]):
            return 0.0
        last = df.iloc[-1]

        adx_val = last["ADX"]
        if pd.isna(adx_val) or adx_val < 20:
            return 0.0  # No trend

        # Direction from DI
        if last["Plus_DI"] > last["Minus_DI"]:
            direction = 1.0
        else:
            direction = -1.0

        # Strength multiplier (ADX 20-60 mapped to 0.3-1.0)
        strength = np.clip((adx_val - 20) / 40, 0.3, 1.0)
        return direction * strength

    def _ichimoku_signal(self, df: pd.DataFrame) -> float:
        needed = ["Ichimoku_Tenkan", "Ichimoku_Kijun", "Ichimoku_SenkouA", "Ichimoku_SenkouB"]
        if not all(c in df.columns for c in needed):
            return 0.0

        last = df.iloc[-1]
        close = last["Close"]
        score = 0.0

        # Price above/below cloud
        cloud_top = max(last.get("Ichimoku_SenkouA", 0), last.get("Ichimoku_SenkouB", 0))
        cloud_bottom = min(last.get("Ichimoku_SenkouA", 0), last.get("Ichimoku_SenkouB", 0))

        if pd.isna(cloud_top) or pd.isna(cloud_bottom):
            return 0.0

        if close > cloud_top:
            score += 0.5
        elif close < cloud_bottom:
            score -= 0.5

        # Tenkan/Kijun cross
        if last["Ichimoku_Tenkan"] > last["Ichimoku_Kijun"]:
            score += 0.5
        else:
            score -= 0.5

        return np.clip(score, -1.0, 1.0)

    def _supertrend_signal(self, df: pd.DataFrame) -> float:
        if "Supertrend_Direction" not in df.columns:
            return 0.0
        direction = df["Supertrend_Direction"].iloc[-1]
        if pd.isna(direction):
            return 0.0
        return 1.0 if direction == 1 else -1.0

    def _vwap_signal(self, df: pd.DataFrame) -> float:
        if "VWAP" not in df.columns:
            return 0.0
        last = df.iloc[-1]
        if pd.isna(last["VWAP"]) or last["VWAP"] == 0:
            return 0.0
        pct_diff = (last["Close"] - last["VWAP"]) / last["VWAP"]
        return np.clip(pct_diff * 10, -1.0, 1.0)

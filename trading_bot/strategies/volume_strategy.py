"""
Volume analysis strategy for crude oil futures.
Uses volume patterns to confirm price movements and detect
institutional activity.
"""

import numpy as np
import pandas as pd

from trading_bot.strategies.base_strategy import BaseStrategy, Signal, SignalType


class VolumeStrategy(BaseStrategy):
    """Volume-based confirmation strategy."""

    name = "volume_analysis"
    weight = 0.20

    def analyze(self, df: pd.DataFrame) -> Signal:
        if df.empty or len(df) < 30 or "Volume" not in df.columns:
            return Signal(SignalType.NEUTRAL, 0.0, self.name, {})

        scores = []
        details = {}

        # 1. OBV Trend
        obv_score = self._obv_signal(df)
        scores.append(("obv", obv_score, 0.25))
        details["obv"] = obv_score

        # 2. Volume Price Trend
        vpt_score = self._vpt_signal(df)
        scores.append(("vpt", vpt_score, 0.20))
        details["vpt"] = vpt_score

        # 3. Accumulation/Distribution
        ad_score = self._ad_signal(df)
        scores.append(("ad_line", ad_score, 0.20))
        details["ad_line"] = ad_score

        # 4. Volume Spike Detection
        spike_score = self._volume_spike_signal(df)
        scores.append(("volume_spike", spike_score, 0.20))
        details["volume_spike"] = spike_score

        # 5. Price-Volume Divergence
        div_score = self._price_volume_divergence(df)
        scores.append(("divergence", div_score, 0.15))
        details["divergence"] = div_score

        composite = sum(score * weight for _, score, weight in scores)
        confidence = min(abs(composite), 1.0)

        if composite > 0.10:
            signal_type = SignalType.BUY
        elif composite < -0.10:
            signal_type = SignalType.SELL
        else:
            signal_type = SignalType.NEUTRAL

        return Signal(signal_type, confidence, self.name, details)

    def _obv_signal(self, df: pd.DataFrame) -> float:
        if "OBV" not in df.columns or len(df) < 20:
            return 0.0
        obv = df["OBV"]
        obv_sma = obv.rolling(20).mean()

        last_obv = obv.iloc[-1]
        last_sma = obv_sma.iloc[-1]

        if pd.isna(last_sma) or last_sma == 0:
            return 0.0

        # OBV above its SMA = accumulation, below = distribution
        pct_diff = (last_obv - last_sma) / abs(last_sma)
        return np.clip(pct_diff * 5, -1.0, 1.0)

    def _vpt_signal(self, df: pd.DataFrame) -> float:
        if "VPT" not in df.columns or len(df) < 20:
            return 0.0
        vpt = df["VPT"]
        vpt_sma = vpt.rolling(20).mean()

        last_vpt = vpt.iloc[-1]
        last_sma = vpt_sma.iloc[-1]

        if pd.isna(last_sma) or last_sma == 0:
            return 0.0

        pct_diff = (last_vpt - last_sma) / abs(last_sma)
        return np.clip(pct_diff * 5, -1.0, 1.0)

    def _ad_signal(self, df: pd.DataFrame) -> float:
        if "AD_Line" not in df.columns or len(df) < 20:
            return 0.0
        ad = df["AD_Line"]
        ad_sma = ad.rolling(20).mean()

        last_ad = ad.iloc[-1]
        last_sma = ad_sma.iloc[-1]

        if pd.isna(last_sma) or last_sma == 0:
            return 0.0

        pct_diff = (last_ad - last_sma) / abs(last_sma)
        return np.clip(pct_diff * 5, -1.0, 1.0)

    def _volume_spike_signal(self, df: pd.DataFrame) -> float:
        """Detect unusual volume (institutional activity)."""
        vol = df["Volume"]
        avg_vol = vol.rolling(20).mean()
        last_vol = vol.iloc[-1]
        last_avg = avg_vol.iloc[-1]

        if pd.isna(last_avg) or last_avg == 0:
            return 0.0

        ratio = last_vol / last_avg
        price_change = df["Close"].pct_change().iloc[-1]

        if pd.isna(price_change):
            return 0.0

        # High volume + price up = bullish confirmation
        # High volume + price down = bearish confirmation
        if ratio > 2.0:  # Volume spike
            return np.clip(np.sign(price_change) * min(ratio / 3, 1.0), -1.0, 1.0)
        return 0.0

    def _price_volume_divergence(self, df: pd.DataFrame) -> float:
        """Detect divergence between price and volume trends."""
        if len(df) < 20:
            return 0.0

        close = df["Close"].iloc[-20:]
        vol = df["Volume"].iloc[-20:]

        # Simple linear regression slope for both
        x = np.arange(len(close))

        price_slope = np.polyfit(x, close.values, 1)[0]
        vol_slope = np.polyfit(x, vol.values, 1)[0]

        # Normalize slopes
        price_dir = np.sign(price_slope)
        vol_dir = np.sign(vol_slope)

        # Divergence: price up but volume declining = bearish warning
        if price_dir > 0 and vol_dir < 0:
            return -0.5  # Bearish divergence
        elif price_dir < 0 and vol_dir > 0:
            return 0.5   # Potential reversal (accumulation)
        elif price_dir > 0 and vol_dir > 0:
            return 0.3   # Confirmation
        elif price_dir < 0 and vol_dir < 0:
            return -0.3  # Confirmed downtrend
        return 0.0

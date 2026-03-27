"""
Comprehensive technical indicators engine for crude oil futures analysis.
Calculates 30+ indicators across all timeframes for maximum signal accuracy.
"""

import numpy as np
import pandas as pd


class TechnicalIndicators:
    """Calculate all technical indicators on OHLCV data."""

    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Add all technical indicators to a DataFrame with OHLCV columns."""
        if df.empty or len(df) < 30:
            return df

        ti = TechnicalIndicators
        df = df.copy()

        # --- Trend Indicators ---
        df = ti.sma(df, periods=[10, 20, 50, 100, 200])
        df = ti.ema(df, periods=[9, 12, 21, 26, 50])
        df = ti.macd(df)
        df = ti.adx(df)
        df = ti.ichimoku(df)
        df = ti.supertrend(df)
        df = ti.vwap(df)

        # --- Momentum Indicators ---
        df = ti.rsi(df)
        df = ti.stochastic(df)
        df = ti.williams_r(df)
        df = ti.cci(df)
        df = ti.roc(df)
        df = ti.mfi(df)

        # --- Volatility Indicators ---
        df = ti.bollinger_bands(df)
        df = ti.atr(df)
        df = ti.keltner_channels(df)
        df = ti.historical_volatility(df)

        # --- Volume Indicators ---
        df = ti.obv(df)
        df = ti.vpt(df)
        df = ti.accumulation_distribution(df)

        # --- Support/Resistance ---
        df = ti.pivot_points(df)
        df = ti.donchian_channels(df)

        return df

    # ===================== TREND =====================

    @staticmethod
    def sma(df: pd.DataFrame, periods: list[int] = None) -> pd.DataFrame:
        for p in (periods or [20, 50, 200]):
            if len(df) >= p:
                df[f"SMA_{p}"] = df["Close"].rolling(window=p).mean()
        return df

    @staticmethod
    def ema(df: pd.DataFrame, periods: list[int] = None) -> pd.DataFrame:
        for p in (periods or [9, 21, 50]):
            if len(df) >= p:
                df[f"EMA_{p}"] = df["Close"].ewm(span=p, adjust=False).mean()
        return df

    @staticmethod
    def macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        if len(df) < slow + signal:
            return df
        ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
        ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
        df["MACD"] = ema_fast - ema_slow
        df["MACD_Signal"] = df["MACD"].ewm(span=signal, adjust=False).mean()
        df["MACD_Histogram"] = df["MACD"] - df["MACD_Signal"]
        return df

    @staticmethod
    def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        if len(df) < period * 2:
            return df
        high, low, close = df["High"], df["Low"], df["Close"]

        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)

        atr = tr.ewm(alpha=1/period, min_periods=period).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
        df["ADX"] = dx.ewm(alpha=1/period, min_periods=period).mean()
        df["Plus_DI"] = plus_di
        df["Minus_DI"] = minus_di
        return df

    @staticmethod
    def ichimoku(df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < 52:
            return df
        high, low = df["High"], df["Low"]

        tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
        kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
        senkou_a = ((tenkan + kijun) / 2).shift(26)
        senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
        chikou = df["Close"].shift(-26)

        df["Ichimoku_Tenkan"] = tenkan
        df["Ichimoku_Kijun"] = kijun
        df["Ichimoku_SenkouA"] = senkou_a
        df["Ichimoku_SenkouB"] = senkou_b
        df["Ichimoku_Chikou"] = chikou
        return df

    @staticmethod
    def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
        if len(df) < period:
            return df
        high, low, close = df["High"], df["Low"], df["Close"]
        hl2 = (high + low) / 2

        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, min_periods=period).mean()

        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr

        supertrend = pd.Series(np.nan, index=df.index)
        direction = pd.Series(1, index=df.index)  # 1 = up, -1 = down

        for i in range(period, len(df)):
            if close.iloc[i] > upper_band.iloc[i - 1]:
                direction.iloc[i] = 1
            elif close.iloc[i] < lower_band.iloc[i - 1]:
                direction.iloc[i] = -1
            else:
                direction.iloc[i] = direction.iloc[i - 1]

            if direction.iloc[i] == 1:
                supertrend.iloc[i] = lower_band.iloc[i]
            else:
                supertrend.iloc[i] = upper_band.iloc[i]

        df["Supertrend"] = supertrend
        df["Supertrend_Direction"] = direction
        return df

    @staticmethod
    def vwap(df: pd.DataFrame) -> pd.DataFrame:
        if "Volume" not in df.columns or len(df) < 2:
            return df
        typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
        vol = df["Volume"].replace(0, np.nan)
        df["VWAP"] = (typical_price * vol).cumsum() / vol.cumsum()
        return df

    # ===================== MOMENTUM =====================

    @staticmethod
    def rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        if len(df) < period + 1:
            return df
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        df["RSI"] = 100 - (100 / (1 + rs))
        return df

    @staticmethod
    def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
        if len(df) < k_period + d_period:
            return df
        low_min = df["Low"].rolling(k_period).min()
        high_max = df["High"].rolling(k_period).max()
        denom = (high_max - low_min).replace(0, np.nan)

        df["Stoch_K"] = 100 * (df["Close"] - low_min) / denom
        df["Stoch_D"] = df["Stoch_K"].rolling(d_period).mean()
        return df

    @staticmethod
    def williams_r(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        if len(df) < period:
            return df
        high_max = df["High"].rolling(period).max()
        low_min = df["Low"].rolling(period).min()
        denom = (high_max - low_min).replace(0, np.nan)
        df["Williams_R"] = -100 * (high_max - df["Close"]) / denom
        return df

    @staticmethod
    def cci(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        if len(df) < period:
            return df
        tp = (df["High"] + df["Low"] + df["Close"]) / 3
        sma = tp.rolling(period).mean()
        mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        df["CCI"] = (tp - sma) / (0.015 * mad.replace(0, np.nan))
        return df

    @staticmethod
    def roc(df: pd.DataFrame, period: int = 12) -> pd.DataFrame:
        if len(df) < period:
            return df
        df["ROC"] = df["Close"].pct_change(periods=period) * 100
        return df

    @staticmethod
    def mfi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        if len(df) < period or "Volume" not in df.columns:
            return df
        tp = (df["High"] + df["Low"] + df["Close"]) / 3
        raw_mf = tp * df["Volume"]

        pos_mf = raw_mf.where(tp > tp.shift(1), 0.0).rolling(period).sum()
        neg_mf = raw_mf.where(tp < tp.shift(1), 0.0).rolling(period).sum()

        mfr = pos_mf / neg_mf.replace(0, np.nan)
        df["MFI"] = 100 - (100 / (1 + mfr))
        return df

    # ===================== VOLATILITY =====================

    @staticmethod
    def bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        if len(df) < period:
            return df
        sma = df["Close"].rolling(period).mean()
        std = df["Close"].rolling(period).std()
        df["BB_Upper"] = sma + std_dev * std
        df["BB_Middle"] = sma
        df["BB_Lower"] = sma - std_dev * std
        df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Middle"]
        df["BB_Position"] = (df["Close"] - df["BB_Lower"]) / (df["BB_Upper"] - df["BB_Lower"]).replace(0, np.nan)
        return df

    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        if len(df) < period:
            return df
        tr = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs()
        ], axis=1).max(axis=1)
        df["ATR"] = tr.ewm(alpha=1/period, min_periods=period).mean()
        df["ATR_Pct"] = df["ATR"] / df["Close"] * 100
        return df

    @staticmethod
    def keltner_channels(df: pd.DataFrame, ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0) -> pd.DataFrame:
        if len(df) < max(ema_period, atr_period):
            return df
        ema = df["Close"].ewm(span=ema_period, adjust=False).mean()

        tr = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - df["Close"].shift()).abs(),
            (df["Low"] - df["Close"].shift()).abs()
        ], axis=1).max(axis=1)
        atr_val = tr.ewm(alpha=1/atr_period, min_periods=atr_period).mean()

        df["Keltner_Upper"] = ema + multiplier * atr_val
        df["Keltner_Middle"] = ema
        df["Keltner_Lower"] = ema - multiplier * atr_val
        return df

    @staticmethod
    def historical_volatility(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        if len(df) < period:
            return df
        log_returns = np.log(df["Close"] / df["Close"].shift(1))
        df["HV"] = log_returns.rolling(period).std() * np.sqrt(252) * 100
        return df

    # ===================== VOLUME =====================

    @staticmethod
    def obv(df: pd.DataFrame) -> pd.DataFrame:
        if "Volume" not in df.columns or len(df) < 2:
            return df
        sign = np.sign(df["Close"].diff())
        df["OBV"] = (sign * df["Volume"]).cumsum()
        return df

    @staticmethod
    def vpt(df: pd.DataFrame) -> pd.DataFrame:
        if "Volume" not in df.columns or len(df) < 2:
            return df
        pct = df["Close"].pct_change()
        df["VPT"] = (pct * df["Volume"]).cumsum()
        return df

    @staticmethod
    def accumulation_distribution(df: pd.DataFrame) -> pd.DataFrame:
        if "Volume" not in df.columns or len(df) < 2:
            return df
        hl = (df["High"] - df["Low"]).replace(0, np.nan)
        clv = ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / hl
        df["AD_Line"] = (clv * df["Volume"]).cumsum()
        return df

    # ===================== SUPPORT / RESISTANCE =====================

    @staticmethod
    def pivot_points(df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < 2:
            return df
        pp = (df["High"].shift(1) + df["Low"].shift(1) + df["Close"].shift(1)) / 3
        df["Pivot"] = pp
        df["R1"] = 2 * pp - df["Low"].shift(1)
        df["S1"] = 2 * pp - df["High"].shift(1)
        df["R2"] = pp + (df["High"].shift(1) - df["Low"].shift(1))
        df["S2"] = pp - (df["High"].shift(1) - df["Low"].shift(1))
        return df

    @staticmethod
    def donchian_channels(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        if len(df) < period:
            return df
        df["Donchian_Upper"] = df["High"].rolling(period).max()
        df["Donchian_Lower"] = df["Low"].rolling(period).min()
        df["Donchian_Middle"] = (df["Donchian_Upper"] + df["Donchian_Lower"]) / 2
        return df

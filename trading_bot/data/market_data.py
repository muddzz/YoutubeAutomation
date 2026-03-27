"""
Multi-timeframe market data fetcher for crude oil futures.
Supports minute, hourly, daily, weekly, monthly, and yearly data.
Uses yfinance for historical data and can integrate with broker APIs for live data.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

CRUDE_OIL_SYMBOL = "CL=F"  # WTI Crude Oil Futures (CME)
BRENT_SYMBOL = "BZ=F"      # Brent Crude Oil Futures


class Timeframe(Enum):
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    DAILY = "1d"
    WEEKLY = "1wk"
    MONTHLY = "1mo"


# Maximum lookback periods for yfinance by interval
LOOKBACK_LIMITS = {
    Timeframe.MINUTE_1: 7,       # 7 days
    Timeframe.MINUTE_5: 60,      # 60 days
    Timeframe.MINUTE_15: 60,
    Timeframe.MINUTE_30: 60,
    Timeframe.HOUR_1: 730,       # ~2 years
    Timeframe.DAILY: 7300,       # ~20 years
    Timeframe.WEEKLY: 7300,
    Timeframe.MONTHLY: 7300,
}


@dataclass
class MarketSnapshot:
    """Complete market snapshot across all timeframes."""
    symbol: str
    timestamp: datetime
    timeframes: dict = field(default_factory=dict)  # Timeframe -> DataFrame
    spread_data: Optional[pd.DataFrame] = None  # WTI-Brent spread


class MarketDataFetcher:
    """Fetches and manages crude oil market data across multiple timeframes."""

    def __init__(self, symbol: str = CRUDE_OIL_SYMBOL):
        self.symbol = symbol
        self.ticker = yf.Ticker(symbol)
        self._cache: dict[str, pd.DataFrame] = {}

    def fetch_timeframe(
        self,
        timeframe: Timeframe,
        lookback_days: Optional[int] = None,
    ) -> pd.DataFrame:
        """Fetch OHLCV data for a specific timeframe."""
        max_days = LOOKBACK_LIMITS[timeframe]
        days = min(lookback_days or max_days, max_days)

        end = datetime.now()
        start = end - timedelta(days=days)

        cache_key = f"{self.symbol}_{timeframe.value}_{days}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if len(cached) > 0:
                last_cached = cached.index[-1]
                if isinstance(last_cached, pd.Timestamp):
                    # Refresh if stale (older than the timeframe interval)
                    staleness = _timeframe_to_minutes(timeframe)
                    if (end - last_cached.to_pydatetime().replace(tzinfo=None)).total_seconds() < staleness * 60:
                        return cached

        logger.info(f"Fetching {timeframe.value} data for {self.symbol} ({days} days)")

        try:
            df = yf.download(
                self.symbol,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                interval=timeframe.value,
                progress=False,
                auto_adjust=True,
            )
            if df.empty:
                logger.warning(f"No data returned for {self.symbol} {timeframe.value}")
                return pd.DataFrame()

            # Flatten multi-level columns if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.dropna()
            self._cache[cache_key] = df
            return df

        except Exception as e:
            logger.error(f"Failed to fetch {timeframe.value} data: {e}")
            return pd.DataFrame()

    def fetch_all_timeframes(self) -> dict[Timeframe, pd.DataFrame]:
        """Fetch data across all supported timeframes."""
        data = {}
        for tf in Timeframe:
            df = self.fetch_timeframe(tf)
            if not df.empty:
                data[tf] = df
        return data

    def fetch_analysis_timeframes(self) -> dict[Timeframe, pd.DataFrame]:
        """Fetch the key timeframes used for multi-timeframe analysis."""
        key_timeframes = [
            (Timeframe.MINUTE_5, 30),     # 30 days of 5-min data
            (Timeframe.HOUR_1, 365),      # 1 year of hourly data
            (Timeframe.DAILY, 2000),      # ~5.5 years of daily data
            (Timeframe.WEEKLY, 5000),     # ~14 years of weekly data
            (Timeframe.MONTHLY, 7300),    # ~20 years of monthly data
        ]
        data = {}
        for tf, days in key_timeframes:
            df = self.fetch_timeframe(tf, lookback_days=days)
            if not df.empty:
                data[tf] = df
        return data

    def get_wti_brent_spread(self, timeframe: Timeframe = Timeframe.DAILY) -> pd.DataFrame:
        """Calculate WTI-Brent spread for analysis."""
        wti = self.fetch_timeframe(timeframe)
        brent_fetcher = MarketDataFetcher(BRENT_SYMBOL)
        brent = brent_fetcher.fetch_timeframe(timeframe)

        if wti.empty or brent.empty:
            return pd.DataFrame()

        common_idx = wti.index.intersection(brent.index)
        spread = pd.DataFrame(index=common_idx)
        spread["wti_close"] = wti.loc[common_idx, "Close"]
        spread["brent_close"] = brent.loc[common_idx, "Close"]
        spread["spread"] = spread["wti_close"] - spread["brent_close"]
        spread["spread_pct"] = spread["spread"] / spread["brent_close"] * 100
        return spread

    def get_market_snapshot(self) -> MarketSnapshot:
        """Get a complete market snapshot."""
        snapshot = MarketSnapshot(
            symbol=self.symbol,
            timestamp=datetime.now(),
        )
        snapshot.timeframes = self.fetch_analysis_timeframes()

        try:
            snapshot.spread_data = self.get_wti_brent_spread()
        except Exception as e:
            logger.warning(f"Could not fetch spread data: {e}")

        return snapshot

    def get_current_price(self) -> Optional[float]:
        """Get the most recent price."""
        try:
            df = self.fetch_timeframe(Timeframe.MINUTE_5, lookback_days=1)
            if not df.empty:
                return float(df["Close"].iloc[-1])
        except Exception:
            pass

        try:
            info = self.ticker.info
            return info.get("regularMarketPrice") or info.get("previousClose")
        except Exception as e:
            logger.error(f"Could not get current price: {e}")
            return None


def _timeframe_to_minutes(tf: Timeframe) -> int:
    mapping = {
        Timeframe.MINUTE_1: 1,
        Timeframe.MINUTE_5: 5,
        Timeframe.MINUTE_15: 15,
        Timeframe.MINUTE_30: 30,
        Timeframe.HOUR_1: 60,
        Timeframe.DAILY: 1440,
        Timeframe.WEEKLY: 10080,
        Timeframe.MONTHLY: 43200,
    }
    return mapping[tf]

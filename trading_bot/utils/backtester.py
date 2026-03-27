"""
Backtesting Engine for the Crude Oil Trading Bot.

Tests strategies against historical data to validate performance
before deploying with real capital.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from trading_bot.data.market_data import MarketDataFetcher, Timeframe
from trading_bot.strategies.base_strategy import SignalType
from trading_bot.strategies.confidence_engine import ConfidenceEngine
from trading_bot.strategies.indicators import TechnicalIndicators
from trading_bot.strategies.mean_reversion_strategy import MeanReversionStrategy
from trading_bot.strategies.momentum_strategy import MomentumStrategy
from trading_bot.strategies.trend_strategy import TrendStrategy
from trading_bot.strategies.volume_strategy import VolumeStrategy

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    entry_idx: int
    entry_price: float
    action: str  # BUY or SELL
    stop_loss: float
    take_profit: float
    confidence: float
    exit_idx: Optional[int] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    exit_reason: str = ""


@dataclass
class BacktestResult:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate_pct: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_confidence_winners: float = 0.0
    avg_confidence_losers: float = 0.0
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)

    def summary(self) -> str:
        return (
            "\n" + "=" * 55 +
            "\n  BACKTEST RESULTS" +
            "\n" + "=" * 55 +
            f"\n  Total Trades:        {self.total_trades}" +
            f"\n  Winning Trades:      {self.winning_trades}" +
            f"\n  Losing Trades:       {self.losing_trades}" +
            f"\n  Win Rate:            {self.win_rate_pct:.1f}%" +
            f"\n  Total P&L:           {self.total_pnl_pct:+.2f}%" +
            f"\n  Avg Win:             {self.avg_win_pct:+.2f}%" +
            f"\n  Avg Loss:            {self.avg_loss_pct:+.2f}%" +
            f"\n  Profit Factor:       {self.profit_factor:.2f}" +
            f"\n  Sharpe Ratio:        {self.sharpe_ratio:.2f}" +
            f"\n  Max Drawdown:        {self.max_drawdown_pct:.2f}%" +
            f"\n  Max Consec. Wins:    {self.max_consecutive_wins}" +
            f"\n  Max Consec. Losses:  {self.max_consecutive_losses}" +
            f"\n  Avg Conf (winners):  {self.avg_confidence_winners:.1f}%" +
            f"\n  Avg Conf (losers):   {self.avg_confidence_losers:.1f}%" +
            "\n" + "=" * 55
        )


class Backtester:
    """
    Walk-forward backtester that simulates the bot's strategy
    on historical data.
    """

    def __init__(
        self,
        timeframe: Timeframe = Timeframe.DAILY,
        lookback_days: int = 2000,
        min_bars_for_analysis: int = 200,
        atr_stop_multiplier: float = 2.0,
        atr_target_multiplier: float = 3.0,
        min_confidence: float = 40.0,
    ):
        self.timeframe = timeframe
        self.lookback_days = lookback_days
        self.min_bars = min_bars_for_analysis
        self.atr_stop_mult = atr_stop_multiplier
        self.atr_target_mult = atr_target_multiplier
        self.min_confidence = min_confidence

        self.strategies = [
            TrendStrategy(),
            MeanReversionStrategy(),
            MomentumStrategy(),
            VolumeStrategy(),
        ]

    def run(self, symbol: str = "CL=F") -> BacktestResult:
        """Run backtest on historical data."""
        logger.info(f"Starting backtest for {symbol} on {self.timeframe.value} ({self.lookback_days} days)")

        fetcher = MarketDataFetcher(symbol)
        df = fetcher.fetch_timeframe(self.timeframe, lookback_days=self.lookback_days)

        if df.empty or len(df) < self.min_bars:
            logger.error(f"Insufficient data: {len(df)} bars (need {self.min_bars})")
            return BacktestResult()

        # Add all indicators
        df = TechnicalIndicators.add_all_indicators(df)
        logger.info(f"Backtesting on {len(df)} bars with {len(df.columns)} features")

        trades: list[BacktestTrade] = []
        equity = 100000.0
        equity_curve = [equity]
        current_trade: Optional[BacktestTrade] = None

        # Walk forward from min_bars to end
        for i in range(self.min_bars, len(df)):
            window = df.iloc[:i + 1]
            current_close = float(window["Close"].iloc[-1])
            current_high = float(window["High"].iloc[-1])
            current_low = float(window["Low"].iloc[-1])

            # Check if we need to exit current trade
            if current_trade is not None:
                exit_price, exit_reason = self._check_exit(
                    current_trade, current_high, current_low, current_close
                )
                if exit_price is not None:
                    current_trade.exit_idx = i
                    current_trade.exit_price = exit_price
                    current_trade.exit_reason = exit_reason

                    if current_trade.action == "BUY":
                        current_trade.pnl = (exit_price - current_trade.entry_price) / current_trade.entry_price * 100
                    else:
                        current_trade.pnl = (current_trade.entry_price - exit_price) / current_trade.entry_price * 100

                    # Apply position sizing effect
                    equity_change = equity * (current_trade.pnl / 100) * (current_trade.confidence / 100)
                    equity += equity_change
                    trades.append(current_trade)
                    current_trade = None

            # Look for new entry if no position
            if current_trade is None and i < len(df) - 1:
                signal = self._get_composite_signal(window)
                if signal is not None:
                    action, confidence = signal

                    if confidence >= self.min_confidence:
                        atr_val = self._get_atr(window)
                        if atr_val and atr_val > 0:
                            if action == "BUY":
                                sl = current_close - self.atr_stop_mult * atr_val
                                tp = current_close + self.atr_target_mult * atr_val
                            else:
                                sl = current_close + self.atr_stop_mult * atr_val
                                tp = current_close - self.atr_target_mult * atr_val

                            current_trade = BacktestTrade(
                                entry_idx=i,
                                entry_price=current_close,
                                action=action,
                                stop_loss=sl,
                                take_profit=tp,
                                confidence=confidence,
                            )

            equity_curve.append(equity)

        # Force close any open trade at end
        if current_trade is not None:
            last_close = float(df["Close"].iloc[-1])
            current_trade.exit_idx = len(df) - 1
            current_trade.exit_price = last_close
            current_trade.exit_reason = "end_of_data"
            if current_trade.action == "BUY":
                current_trade.pnl = (last_close - current_trade.entry_price) / current_trade.entry_price * 100
            else:
                current_trade.pnl = (current_trade.entry_price - last_close) / current_trade.entry_price * 100
            trades.append(current_trade)

        return self._compile_results(trades, equity_curve)

    def _get_composite_signal(self, df: pd.DataFrame) -> Optional[tuple[str, float]]:
        """Get composite signal from all strategies."""
        signals = []
        for strategy in self.strategies:
            sig = strategy.analyze(df)
            signals.append(sig)

        if not signals:
            return None

        # Weighted average
        total_score = 0.0
        total_weight = 0.0
        total_confidence = 0.0

        for sig in signals:
            weight = next((s.weight for s in self.strategies if s.name == sig.strategy_name), 0.25)
            total_score += sig.direction * sig.confidence * weight
            total_weight += weight
            total_confidence += sig.confidence * weight

        if total_weight == 0:
            return None

        avg_score = total_score / total_weight
        avg_confidence = total_confidence / total_weight

        if avg_score > 0.10:
            return "BUY", avg_confidence * 100
        elif avg_score < -0.10:
            return "SELL", avg_confidence * 100

        return None

    def _check_exit(
        self, trade: BacktestTrade, high: float, low: float, close: float
    ) -> tuple[Optional[float], str]:
        """Check if stop loss or take profit is hit."""
        if trade.action == "BUY":
            if low <= trade.stop_loss:
                return trade.stop_loss, "stop_loss"
            if high >= trade.take_profit:
                return trade.take_profit, "take_profit"
        else:  # SELL
            if high >= trade.stop_loss:
                return trade.stop_loss, "stop_loss"
            if low <= trade.take_profit:
                return trade.take_profit, "take_profit"
        return None, ""

    def _get_atr(self, df: pd.DataFrame) -> Optional[float]:
        if "ATR" in df.columns:
            val = df["ATR"].iloc[-1]
            return float(val) if not pd.isna(val) else None
        return None

    def _compile_results(self, trades: list[BacktestTrade], equity_curve: list[float]) -> BacktestResult:
        """Compile all trades into a BacktestResult."""
        if not trades:
            return BacktestResult(equity_curve=equity_curve)

        winners = [t for t in trades if t.pnl > 0]
        losers = [t for t in trades if t.pnl <= 0]

        total_win = sum(t.pnl for t in winners) if winners else 0
        total_loss = sum(abs(t.pnl) for t in losers) if losers else 0

        # Consecutive streaks
        max_wins, max_losses = 0, 0
        curr_wins, curr_losses = 0, 0
        for t in trades:
            if t.pnl > 0:
                curr_wins += 1
                curr_losses = 0
                max_wins = max(max_wins, curr_wins)
            else:
                curr_losses += 1
                curr_wins = 0
                max_losses = max(max_losses, curr_losses)

        # Sharpe ratio from equity curve
        if len(equity_curve) > 1:
            returns = pd.Series(equity_curve).pct_change().dropna()
            sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
        else:
            sharpe = 0

        # Max drawdown
        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100
            max_dd = max(max_dd, dd)

        return BacktestResult(
            total_trades=len(trades),
            winning_trades=len(winners),
            losing_trades=len(losers),
            total_pnl_pct=round(sum(t.pnl for t in trades), 2),
            max_drawdown_pct=round(max_dd, 2),
            win_rate_pct=round(len(winners) / len(trades) * 100, 1) if trades else 0,
            avg_win_pct=round(total_win / len(winners), 2) if winners else 0,
            avg_loss_pct=round(-total_loss / len(losers), 2) if losers else 0,
            profit_factor=round(total_win / total_loss, 2) if total_loss > 0 else float("inf"),
            sharpe_ratio=round(sharpe, 2),
            max_consecutive_wins=max_wins,
            max_consecutive_losses=max_losses,
            avg_confidence_winners=round(np.mean([t.confidence for t in winners]), 1) if winners else 0,
            avg_confidence_losers=round(np.mean([t.confidence for t in losers]), 1) if losers else 0,
            trades=trades,
            equity_curve=equity_curve,
        )

"""
Multi-Timeframe Confidence Scoring Engine.

Aggregates signals from all strategies across all timeframes
and produces a final confidence-weighted trade recommendation.
This is the brain of the trading bot.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from trading_bot.data.market_data import MarketDataFetcher, MarketSnapshot, Timeframe
from trading_bot.strategies.base_strategy import Signal, SignalType
from trading_bot.strategies.indicators import TechnicalIndicators
from trading_bot.strategies.mean_reversion_strategy import MeanReversionStrategy
from trading_bot.strategies.momentum_strategy import MomentumStrategy
from trading_bot.strategies.trend_strategy import TrendStrategy
from trading_bot.strategies.volume_strategy import VolumeStrategy

logger = logging.getLogger(__name__)

# Timeframe weights — higher timeframes get more weight for reliability
TIMEFRAME_WEIGHTS = {
    Timeframe.MINUTE_5: 0.05,
    Timeframe.MINUTE_15: 0.07,
    Timeframe.MINUTE_30: 0.08,
    Timeframe.HOUR_1: 0.15,
    Timeframe.DAILY: 0.30,
    Timeframe.WEEKLY: 0.20,
    Timeframe.MONTHLY: 0.15,
}


@dataclass
class TradeRecommendation:
    """Final trade recommendation with full analysis."""
    timestamp: datetime
    symbol: str
    action: str                        # "BUY", "SELL", "HOLD"
    confidence_pct: float              # 0-100%
    current_price: Optional[float]
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit_1: Optional[float]
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    position_size_pct: float           # % of capital to risk
    risk_reward_ratio: float
    timeframe_signals: dict = field(default_factory=dict)
    strategy_signals: dict = field(default_factory=dict)
    reasoning: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "=" * 60,
            f"  CRUDE OIL FUTURES TRADE RECOMMENDATION",
            f"  {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "=" * 60,
            f"  Symbol:          {self.symbol}",
            f"  Action:          {self.action}",
            f"  Confidence:      {self.confidence_pct:.1f}%",
            f"  Current Price:   ${self.current_price:.2f}" if self.current_price else "",
            f"  Entry Price:     ${self.entry_price:.2f}" if self.entry_price else "",
            f"  Stop Loss:       ${self.stop_loss:.2f}" if self.stop_loss else "",
            f"  Take Profit 1:   ${self.take_profit_1:.2f}" if self.take_profit_1 else "",
            f"  Take Profit 2:   ${self.take_profit_2:.2f}" if self.take_profit_2 else "",
            f"  Take Profit 3:   ${self.take_profit_3:.2f}" if self.take_profit_3 else "",
            f"  Position Size:   {self.position_size_pct:.1f}% of capital",
            f"  Risk/Reward:     1:{self.risk_reward_ratio:.1f}",
            "-" * 60,
            "  TIMEFRAME ANALYSIS:",
        ]
        for tf, sig in self.timeframe_signals.items():
            lines.append(f"    {tf:12s} -> {sig}")
        lines.append("-" * 60)
        lines.append("  STRATEGY BREAKDOWN:")
        for strat, sig in self.strategy_signals.items():
            lines.append(f"    {strat:20s} -> {sig}")
        lines.append("-" * 60)
        lines.append("  REASONING:")
        for r in self.reasoning:
            lines.append(f"    - {r}")
        lines.append("=" * 60)
        return "\n".join(line for line in lines if line)


class ConfidenceEngine:
    """
    Aggregates signals from multiple strategies across multiple timeframes.
    Produces a single, high-confidence trade recommendation.
    """

    def __init__(self, fetcher: Optional[MarketDataFetcher] = None):
        self.fetcher = fetcher or MarketDataFetcher()
        self.strategies = [
            TrendStrategy(),
            MeanReversionStrategy(),
            MomentumStrategy(),
            VolumeStrategy(),
        ]

    def analyze(self) -> TradeRecommendation:
        """Run full multi-timeframe, multi-strategy analysis."""
        logger.info("Starting multi-timeframe analysis...")
        snapshot = self.fetcher.get_market_snapshot()

        # Analyze each timeframe with each strategy
        all_signals: dict[str, list[tuple[Signal, float]]] = {}  # tf -> [(signal, tf_weight)]
        strategy_aggregates: dict[str, list[Signal]] = {}

        for tf, df in snapshot.timeframes.items():
            tf_weight = TIMEFRAME_WEIGHTS.get(tf, 0.10)
            tf_name = tf.value

            # Add indicators
            df_with_indicators = TechnicalIndicators.add_all_indicators(df)
            logger.info(f"  {tf_name}: {len(df)} bars, {len(df_with_indicators.columns)} features")

            tf_signals = []
            for strategy in self.strategies:
                signal = strategy.analyze(df_with_indicators)
                tf_signals.append((signal, tf_weight))

                strat_name = strategy.name
                if strat_name not in strategy_aggregates:
                    strategy_aggregates[strat_name] = []
                strategy_aggregates[strat_name].append(signal)

            all_signals[tf_name] = tf_signals

        # Compute composite score
        composite_score = self._compute_composite(all_signals)
        confidence = self._compute_confidence(all_signals, composite_score)

        # Determine action
        action, reasoning = self._determine_action(
            composite_score, confidence, all_signals, strategy_aggregates
        )

        # Get current price for entry/exit calculations
        current_price = self.fetcher.get_current_price()

        # Calculate risk management levels
        stop_loss, tp1, tp2, tp3, rr_ratio = self._calculate_levels(
            action, current_price, snapshot
        )

        # Position sizing based on confidence
        position_size = self._calculate_position_size(confidence, rr_ratio)

        # Build timeframe summary
        tf_summary = {}
        for tf_name, signals in all_signals.items():
            avg_dir = np.mean([s.direction * s.confidence for s, _ in signals])
            if avg_dir > 0.1:
                tf_summary[tf_name] = f"BULLISH ({avg_dir:+.2f})"
            elif avg_dir < -0.1:
                tf_summary[tf_name] = f"BEARISH ({avg_dir:+.2f})"
            else:
                tf_summary[tf_name] = f"NEUTRAL ({avg_dir:+.2f})"

        # Build strategy summary
        strat_summary = {}
        for strat_name, signals in strategy_aggregates.items():
            avg_dir = np.mean([s.direction * s.confidence for s in signals])
            avg_conf = np.mean([s.confidence for s in signals])
            strat_summary[strat_name] = (
                f"{'BUY' if avg_dir > 0 else 'SELL' if avg_dir < 0 else 'HOLD'} "
                f"(score={avg_dir:+.2f}, conf={avg_conf:.0%})"
            )

        return TradeRecommendation(
            timestamp=datetime.utcnow(),
            symbol=self.fetcher.symbol,
            action=action,
            confidence_pct=confidence * 100,
            current_price=current_price,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            position_size_pct=position_size,
            risk_reward_ratio=rr_ratio,
            timeframe_signals=tf_summary,
            strategy_signals=strat_summary,
            reasoning=reasoning,
        )

    def _compute_composite(self, all_signals: dict) -> float:
        """Compute weighted composite score across all timeframes and strategies."""
        total_score = 0.0
        total_weight = 0.0

        for tf_name, signals in all_signals.items():
            for signal, tf_weight in signals:
                strat_weight = self._get_strategy_weight(signal.strategy_name)
                combined_weight = tf_weight * strat_weight
                total_score += signal.direction * signal.confidence * combined_weight
                total_weight += combined_weight

        if total_weight == 0:
            return 0.0
        return total_score / total_weight

    def _compute_confidence(self, all_signals: dict, composite_score: float) -> float:
        """
        Compute overall confidence based on:
        1. Agreement between strategies
        2. Agreement between timeframes
        3. Strength of individual signals
        """
        # Factor 1: Strategy agreement
        strategy_directions = {}
        for tf_name, signals in all_signals.items():
            for signal, _ in signals:
                name = signal.strategy_name
                if name not in strategy_directions:
                    strategy_directions[name] = []
                strategy_directions[name].append(signal.direction)

        # What % of strategy instances agree on direction?
        all_directions = []
        for dirs in strategy_directions.values():
            all_directions.extend(dirs)

        if not all_directions:
            return 0.0

        dominant_dir = np.sign(composite_score)
        if dominant_dir == 0:
            return 0.0

        agreement_ratio = sum(1 for d in all_directions if d == dominant_dir) / len(all_directions)

        # Factor 2: Timeframe alignment
        tf_directions = {}
        for tf_name, signals in all_signals.items():
            tf_avg = np.mean([s.direction * s.confidence for s, _ in signals])
            tf_directions[tf_name] = np.sign(tf_avg)

        tf_agreement = sum(1 for d in tf_directions.values() if d == dominant_dir) / max(len(tf_directions), 1)

        # Factor 3: Signal strength
        avg_confidence = np.mean([s.confidence for sigs in all_signals.values() for s, _ in sigs])

        # Weighted confidence
        confidence = (
            0.35 * agreement_ratio +
            0.35 * tf_agreement +
            0.30 * avg_confidence
        )

        # Penalize if conflicting signals
        if agreement_ratio < 0.5:
            confidence *= 0.6

        # Boost if all timeframes agree
        if tf_agreement > 0.8:
            confidence = min(confidence * 1.2, 0.98)

        return np.clip(confidence, 0.0, 0.98)  # Never 100% — markets are uncertain

    def _determine_action(
        self,
        composite_score: float,
        confidence: float,
        all_signals: dict,
        strategy_aggregates: dict,
    ) -> tuple[str, list[str]]:
        """Determine final action with reasoning."""
        reasoning = []

        # Check minimum confidence threshold
        MIN_CONFIDENCE = 0.35  # 35% minimum to trade

        if confidence < MIN_CONFIDENCE:
            reasoning.append(f"Confidence {confidence:.0%} below minimum threshold {MIN_CONFIDENCE:.0%}")
            reasoning.append("Mixed signals across timeframes — staying out")
            return "HOLD", reasoning

        if composite_score > 0.10:
            action = "BUY"
            reasoning.append(f"Composite score {composite_score:+.3f} indicates bullish bias")
        elif composite_score < -0.10:
            action = "SELL"
            reasoning.append(f"Composite score {composite_score:+.3f} indicates bearish bias")
        else:
            reasoning.append(f"Composite score {composite_score:+.3f} is indecisive")
            return "HOLD", reasoning

        # Add strategy-level reasoning
        for strat_name, signals in strategy_aggregates.items():
            avg_dir = np.mean([s.direction * s.confidence for s in signals])
            if abs(avg_dir) > 0.2:
                direction = "bullish" if avg_dir > 0 else "bearish"
                reasoning.append(f"{strat_name} strategy is {direction} ({avg_dir:+.2f})")

        # Check for dangerous divergences
        trend_signals = strategy_aggregates.get("trend_following", [])
        mean_rev_signals = strategy_aggregates.get("mean_reversion", [])
        if trend_signals and mean_rev_signals:
            trend_avg = np.mean([s.direction for s in trend_signals])
            mr_avg = np.mean([s.direction for s in mean_rev_signals])
            if np.sign(trend_avg) != np.sign(mr_avg) and abs(trend_avg) > 0.3 and abs(mr_avg) > 0.3:
                reasoning.append("WARNING: Trend and mean-reversion strategies disagree — reduced confidence")

        return action, reasoning

    def _get_strategy_weight(self, strategy_name: str) -> float:
        for s in self.strategies:
            if s.name == strategy_name:
                return s.weight
        return 0.25

    def _calculate_levels(
        self,
        action: str,
        price: Optional[float],
        snapshot: MarketSnapshot,
    ) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float], float]:
        """Calculate stop loss, take profits, and risk/reward ratio using ATR."""
        if price is None or action == "HOLD":
            return None, None, None, None, 0.0

        # Get ATR from daily timeframe for stop/target placement
        atr_value = None
        daily_df = snapshot.timeframes.get(Timeframe.DAILY)
        if daily_df is not None and not daily_df.empty:
            df_ind = TechnicalIndicators.add_all_indicators(daily_df)
            if "ATR" in df_ind.columns:
                atr_value = df_ind["ATR"].iloc[-1]

        if atr_value is None or pd.isna(atr_value):
            atr_value = price * 0.02  # Fallback: 2% of price

        if action == "BUY":
            stop_loss = price - 2.0 * atr_value
            tp1 = price + 1.5 * atr_value
            tp2 = price + 3.0 * atr_value
            tp3 = price + 5.0 * atr_value
        else:  # SELL
            stop_loss = price + 2.0 * atr_value
            tp1 = price - 1.5 * atr_value
            tp2 = price - 3.0 * atr_value
            tp3 = price - 5.0 * atr_value

        risk = abs(price - stop_loss)
        reward = abs(tp2 - price)
        rr_ratio = reward / risk if risk > 0 else 0.0

        return stop_loss, tp1, tp2, tp3, round(rr_ratio, 2)

    def _calculate_position_size(self, confidence: float, rr_ratio: float) -> float:
        """
        Calculate position size as % of capital based on confidence and risk/reward.
        Uses Kelly Criterion-inspired sizing.
        """
        if confidence < 0.35 or rr_ratio < 1.0:
            return 0.0

        # Base position: 1-5% of capital
        # Higher confidence + better RR = larger position
        base = 1.0
        confidence_bonus = confidence * 3.0  # Up to 3% extra
        rr_bonus = min(rr_ratio * 0.5, 2.0)  # Up to 2% extra from RR

        position = base + confidence_bonus + rr_bonus

        # Hard cap at 5% of capital per trade (risk management)
        return min(position, 5.0)

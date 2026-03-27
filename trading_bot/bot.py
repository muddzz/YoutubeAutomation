"""
Main Trading Bot Orchestrator for Crude Oil Futures.

Coordinates data fetching, analysis, risk management, and trade execution.
Supports both live monitoring and paper trading modes.
"""

import logging
import signal
import sys
import time
from datetime import datetime
from typing import Optional

from trading_bot.data.market_data import MarketDataFetcher, CRUDE_OIL_SYMBOL
from trading_bot.strategies.confidence_engine import ConfidenceEngine, TradeRecommendation
from trading_bot.utils.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class CrudeOilTradingBot:
    """
    Main orchestrator for the crude oil futures trading bot.

    Modes:
    - analyze: Run a single analysis and print recommendation
    - monitor: Continuously monitor and alert on opportunities
    - paper: Paper trading mode — simulates trades without real money
    """

    def __init__(
        self,
        symbol: str = CRUDE_OIL_SYMBOL,
        capital: float = 100000.0,
        journal_path: str = "trade_journal.json",
    ):
        self.symbol = symbol
        self.fetcher = MarketDataFetcher(symbol)
        self.engine = ConfidenceEngine(self.fetcher)
        self.risk_manager = RiskManager(capital=capital, journal_path=journal_path)
        self._running = False

    def analyze(self) -> TradeRecommendation:
        """Run a single multi-timeframe analysis and return recommendation."""
        logger.info(f"Analyzing {self.symbol}...")
        recommendation = self.engine.analyze()

        # Apply risk management filter
        can_trade, reason = self.risk_manager.can_trade(
            recommendation.confidence_pct,
            recommendation.risk_reward_ratio,
        )

        if not can_trade:
            recommendation.reasoning.append(f"RISK FILTER: {reason}")
            if recommendation.action != "HOLD":
                recommendation.reasoning.append(
                    f"Original signal was {recommendation.action} but blocked by risk management"
                )
                recommendation.action = "HOLD"

        # Adjust position size through risk manager
        if recommendation.action != "HOLD":
            safe_size = self.risk_manager.calculate_safe_position_size(
                recommendation.confidence_pct,
                recommendation.risk_reward_ratio,
            )
            recommendation.position_size_pct = safe_size

        return recommendation

    def monitor(self, interval_seconds: int = 300, alert_threshold: float = 50.0):
        """
        Continuously monitor the market and alert on high-confidence opportunities.

        Args:
            interval_seconds: Seconds between analyses (default 5 min)
            alert_threshold: Minimum confidence % to trigger alert
        """
        self._running = True
        signal.signal(signal.SIGINT, self._stop_handler)
        signal.signal(signal.SIGTERM, self._stop_handler)

        print(f"\n{'=' * 60}")
        print(f"  CRUDE OIL FUTURES MONITOR")
        print(f"  Symbol: {self.symbol}")
        print(f"  Interval: {interval_seconds}s")
        print(f"  Alert threshold: {alert_threshold}%")
        print(f"  Press Ctrl+C to stop")
        print(f"{'=' * 60}\n")

        iteration = 0
        while self._running:
            iteration += 1
            try:
                timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n[{timestamp}] Analysis #{iteration}...")

                rec = self.analyze()

                # Print compact status
                price_str = f"${rec.current_price:.2f}" if rec.current_price else "N/A"
                print(f"  Price: {price_str} | Signal: {rec.action} | Confidence: {rec.confidence_pct:.1f}%")

                if rec.confidence_pct >= alert_threshold and rec.action != "HOLD":
                    print("\n" + "!" * 60)
                    print(f"  HIGH CONFIDENCE ALERT: {rec.action} at {rec.confidence_pct:.1f}%")
                    print("!" * 60)
                    print(rec.summary())

                if self._running:
                    time.sleep(interval_seconds)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                if self._running:
                    time.sleep(60)  # Wait a minute on error

        print("\nMonitor stopped.")

    def paper_trade(self, recommendation: TradeRecommendation) -> Optional[str]:
        """
        Execute a paper trade based on a recommendation.
        Returns trade ID if executed, None if blocked.
        """
        if recommendation.action == "HOLD":
            return None

        can_trade, reason = self.risk_manager.can_trade(
            recommendation.confidence_pct,
            recommendation.risk_reward_ratio,
        )
        if not can_trade:
            logger.info(f"Paper trade blocked: {reason}")
            return None

        trade = self.risk_manager.record_trade_entry(
            symbol=recommendation.symbol,
            action=recommendation.action,
            entry_price=recommendation.entry_price or 0,
            stop_loss=recommendation.stop_loss or 0,
            take_profit=recommendation.take_profit_2 or 0,
            position_size_pct=recommendation.position_size_pct,
            confidence_pct=recommendation.confidence_pct,
        )

        logger.info(f"Paper trade entered: {trade.trade_id} {trade.action} at ${trade.entry_price:.2f}")
        return trade.trade_id

    def check_open_trades(self):
        """Check open paper trades against current price for exits."""
        current_price = self.fetcher.get_current_price()
        if current_price is None:
            return

        for trade in self.risk_manager.trades:
            if trade.status != "OPEN":
                continue

            exit_price = None
            reason = ""

            if trade.action == "BUY":
                if current_price <= trade.stop_loss:
                    exit_price = trade.stop_loss
                    reason = "stop_loss"
                elif current_price >= trade.take_profit:
                    exit_price = trade.take_profit
                    reason = "take_profit"
            else:  # SELL
                if current_price >= trade.stop_loss:
                    exit_price = trade.stop_loss
                    reason = "stop_loss"
                elif current_price <= trade.take_profit:
                    exit_price = trade.take_profit
                    reason = "take_profit"

            if exit_price is not None:
                result = self.risk_manager.record_trade_exit(trade.trade_id, exit_price, reason)
                if result:
                    emoji = "+" if result.pnl and result.pnl > 0 else ""
                    logger.info(
                        f"Trade {result.trade_id} closed ({reason}): "
                        f"P&L {emoji}{result.pnl_pct:.2f}%"
                    )

    def performance_report(self) -> str:
        """Generate a performance report."""
        stats = self.risk_manager.get_performance_stats()
        lines = [
            "=" * 55,
            "  PERFORMANCE REPORT",
            "=" * 55,
        ]
        for key, val in stats.items():
            label = key.replace("_", " ").title()
            lines.append(f"  {label:25s}: {val}")
        lines.append("=" * 55)
        return "\n".join(lines)

    def _stop_handler(self, signum, frame):
        print("\nStopping...")
        self._running = False

#!/usr/bin/env python3
"""
CLI runner for the Crude Oil Futures Trading Bot.

Usage:
    python -m trading_bot.run analyze          # Single analysis
    python -m trading_bot.run monitor          # Continuous monitoring
    python -m trading_bot.run backtest         # Run backtest on historical data
    python -m trading_bot.run performance      # View performance report
"""

import argparse
import logging
import sys

from trading_bot.bot import CrudeOilTradingBot
from trading_bot.config import BotConfig
from trading_bot.data.market_data import Timeframe
from trading_bot.utils.backtester import Backtester


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Suppress noisy loggers
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("peewee").setLevel(logging.WARNING)


def cmd_analyze(args, config: BotConfig):
    """Run a single analysis."""
    bot = CrudeOilTradingBot(
        symbol=config.symbol,
        capital=config.starting_capital,
        journal_path=config.journal_path,
    )
    rec = bot.analyze()
    print(rec.summary())

    if args.paper_trade and rec.action != "HOLD":
        trade_id = bot.paper_trade(rec)
        if trade_id:
            print(f"\nPaper trade recorded: {trade_id}")


def cmd_monitor(args, config: BotConfig):
    """Start continuous monitoring."""
    bot = CrudeOilTradingBot(
        symbol=config.symbol,
        capital=config.starting_capital,
        journal_path=config.journal_path,
    )
    bot.monitor(
        interval_seconds=config.monitor_interval_seconds,
        alert_threshold=config.alert_threshold,
    )


def cmd_backtest(args, config: BotConfig):
    """Run backtesting."""
    timeframe_map = {
        "1d": Timeframe.DAILY,
        "1h": Timeframe.HOUR_1,
        "1wk": Timeframe.WEEKLY,
    }
    tf = timeframe_map.get(args.timeframe, Timeframe.DAILY)

    backtester = Backtester(
        timeframe=tf,
        lookback_days=args.lookback_days,
        min_confidence=args.min_confidence,
        atr_stop_multiplier=config.atr_stop_multiplier,
        atr_target_multiplier=config.atr_target_multiplier,
    )

    result = backtester.run(symbol=config.symbol)
    print(result.summary())

    if result.total_trades > 0:
        print(f"\n  Confidence filter effectiveness:")
        print(f"    Winners avg confidence: {result.avg_confidence_winners:.1f}%")
        print(f"    Losers avg confidence:  {result.avg_confidence_losers:.1f}%")
        diff = result.avg_confidence_winners - result.avg_confidence_losers
        if diff > 0:
            print(f"    --> Higher confidence trades ARE more accurate (+{diff:.1f}%)")
        else:
            print(f"    --> Confidence filter needs calibration")


def cmd_performance(args, config: BotConfig):
    """Show performance report."""
    bot = CrudeOilTradingBot(
        symbol=config.symbol,
        capital=config.starting_capital,
        journal_path=config.journal_path,
    )
    print(bot.performance_report())


def main():
    parser = argparse.ArgumentParser(
        description="Crude Oil Futures Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m trading_bot.run analyze                 # Single analysis
  python -m trading_bot.run analyze --paper-trade   # Analyze and paper trade
  python -m trading_bot.run monitor                 # Continuous monitoring
  python -m trading_bot.run backtest --days 1000    # Backtest on 1000 days
  python -m trading_bot.run performance             # View stats
        """,
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--symbol", default="CL=F", help="Futures symbol (default: CL=F for WTI)")
    parser.add_argument("--capital", type=float, default=100000, help="Starting capital in USD")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Analyze
    p_analyze = subparsers.add_parser("analyze", help="Run single analysis")
    p_analyze.add_argument("--paper-trade", action="store_true", help="Record as paper trade")

    # Monitor
    p_monitor = subparsers.add_parser("monitor", help="Continuous monitoring")
    p_monitor.add_argument("--interval", type=int, default=300, help="Seconds between analyses")
    p_monitor.add_argument("--threshold", type=float, default=50.0, help="Alert threshold %%")

    # Backtest
    p_backtest = subparsers.add_parser("backtest", help="Run backtesting")
    p_backtest.add_argument("--days", dest="lookback_days", type=int, default=2000, help="Days of history")
    p_backtest.add_argument("--timeframe", default="1d", choices=["1h", "1d", "1wk"], help="Timeframe")
    p_backtest.add_argument("--min-confidence", type=float, default=40.0, help="Min confidence to trade")

    # Performance
    subparsers.add_parser("performance", help="Show performance report")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    setup_logging(args.verbose)

    config = BotConfig(
        symbol=args.symbol,
        starting_capital=args.capital,
    )

    if args.command == "monitor" and hasattr(args, "interval"):
        config.monitor_interval_seconds = args.interval
        config.alert_threshold = args.threshold

    commands = {
        "analyze": cmd_analyze,
        "monitor": cmd_monitor,
        "backtest": cmd_backtest,
        "performance": cmd_performance,
    }

    commands[args.command](args, config)


if __name__ == "__main__":
    main()

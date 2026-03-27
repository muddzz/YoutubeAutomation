"""
Configuration for the Crude Oil Trading Bot.
"""

from dataclasses import dataclass, field


@dataclass
class BotConfig:
    """All configurable parameters for the trading bot."""

    # Symbol
    symbol: str = "CL=F"                    # WTI Crude Oil Futures

    # Capital & Risk
    starting_capital: float = 100000.0       # Starting capital in USD
    max_position_size_pct: float = 5.0       # Max % of capital per trade
    max_daily_loss_pct: float = 3.0          # Stop trading after this daily loss
    max_drawdown_pct: float = 15.0           # Stop trading after this drawdown
    max_open_positions: int = 3
    max_daily_trades: int = 10

    # Signal Thresholds
    min_confidence_to_trade: float = 35.0    # Minimum confidence % to enter
    min_risk_reward: float = 1.5             # Minimum risk/reward ratio
    alert_threshold: float = 50.0            # Alert if confidence above this

    # ATR-based levels
    atr_stop_multiplier: float = 2.0         # Stop loss = price +/- ATR * this
    atr_target_multiplier: float = 3.0       # Take profit = price +/- ATR * this

    # Monitor mode
    monitor_interval_seconds: int = 300      # 5 minutes between analyses

    # Paths
    journal_path: str = "trade_journal.json"

    # Strategy weights (must sum to 1.0)
    strategy_weights: dict = field(default_factory=lambda: {
        "trend_following": 0.30,
        "mean_reversion": 0.25,
        "momentum": 0.25,
        "volume_analysis": 0.20,
    })

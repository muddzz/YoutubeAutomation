"""
Risk Management Module for crude oil futures trading.

Implements:
- Maximum drawdown protection
- Position sizing limits
- Daily loss limits
- Correlation-based exposure management
- Trade journaling for performance tracking
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Record of a single trade for journaling."""
    trade_id: str
    timestamp: str
    symbol: str
    action: str          # BUY or SELL
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size_pct: float
    confidence_pct: float
    exit_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    status: str = "OPEN"  # OPEN, CLOSED, STOPPED_OUT


@dataclass
class RiskState:
    """Current risk state of the portfolio."""
    capital: float = 100000.0           # Starting capital
    current_capital: float = 100000.0
    max_capital: float = 100000.0       # High-water mark
    daily_pnl: float = 0.0
    daily_trades: int = 0
    open_positions: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    max_drawdown_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    last_reset_date: str = ""


class RiskManager:
    """
    Manages risk across all trades.
    Prevents catastrophic losses through multiple safety layers.
    """

    # --- Risk Parameters ---
    MAX_POSITION_SIZE_PCT = 5.0          # Max 5% of capital per trade
    MAX_DAILY_LOSS_PCT = 3.0             # Stop trading if daily loss > 3%
    MAX_DRAWDOWN_PCT = 15.0              # Stop trading if drawdown > 15%
    MAX_OPEN_POSITIONS = 3               # Max concurrent positions
    MAX_DAILY_TRADES = 10                # Max trades per day
    MIN_CONFIDENCE_TO_TRADE = 35.0       # Minimum confidence % to enter
    MIN_RISK_REWARD = 1.5                # Minimum risk/reward ratio
    COOLDOWN_AFTER_LOSS_MINUTES = 30     # Wait 30 min after a loss

    def __init__(self, capital: float = 100000.0, journal_path: str = "trade_journal.json"):
        self.journal_path = Path(journal_path)
        self.state = RiskState(
            capital=capital,
            current_capital=capital,
            max_capital=capital,
            last_reset_date=datetime.utcnow().strftime("%Y-%m-%d"),
        )
        self.trades: list[TradeRecord] = []
        self._last_loss_time: Optional[datetime] = None
        self._load_journal()

    def can_trade(self, confidence_pct: float, risk_reward: float) -> tuple[bool, str]:
        """Check if we're allowed to take a new trade."""
        # Reset daily counters if new day
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if self.state.last_reset_date != today:
            self.state.daily_pnl = 0.0
            self.state.daily_trades = 0
            self.state.last_reset_date = today

        # Check drawdown limit
        self._update_drawdown()
        if self.state.current_drawdown_pct >= self.MAX_DRAWDOWN_PCT:
            return False, f"Max drawdown reached ({self.state.current_drawdown_pct:.1f}% >= {self.MAX_DRAWDOWN_PCT}%)"

        # Check daily loss limit
        daily_loss_pct = abs(self.state.daily_pnl) / self.state.capital * 100
        if self.state.daily_pnl < 0 and daily_loss_pct >= self.MAX_DAILY_LOSS_PCT:
            return False, f"Daily loss limit reached ({daily_loss_pct:.1f}% >= {self.MAX_DAILY_LOSS_PCT}%)"

        # Check max open positions
        if self.state.open_positions >= self.MAX_OPEN_POSITIONS:
            return False, f"Max open positions reached ({self.state.open_positions})"

        # Check max daily trades
        if self.state.daily_trades >= self.MAX_DAILY_TRADES:
            return False, f"Max daily trades reached ({self.state.daily_trades})"

        # Check minimum confidence
        if confidence_pct < self.MIN_CONFIDENCE_TO_TRADE:
            return False, f"Confidence too low ({confidence_pct:.1f}% < {self.MIN_CONFIDENCE_TO_TRADE}%)"

        # Check minimum risk/reward
        if risk_reward < self.MIN_RISK_REWARD:
            return False, f"Risk/reward too low ({risk_reward:.1f} < {self.MIN_RISK_REWARD})"

        # Check cooldown after loss
        if self._last_loss_time:
            elapsed = (datetime.utcnow() - self._last_loss_time).total_seconds() / 60
            if elapsed < self.COOLDOWN_AFTER_LOSS_MINUTES:
                remaining = self.COOLDOWN_AFTER_LOSS_MINUTES - elapsed
                return False, f"Cooling down after loss ({remaining:.0f} min remaining)"

        return True, "All risk checks passed"

    def calculate_safe_position_size(self, confidence_pct: float, risk_reward: float) -> float:
        """Calculate position size with all risk constraints applied."""
        # Base sizing from confidence
        base = min(confidence_pct / 100 * 4.0, self.MAX_POSITION_SIZE_PCT)

        # Scale down if in drawdown
        if self.state.current_drawdown_pct > 5.0:
            drawdown_factor = 1.0 - (self.state.current_drawdown_pct - 5.0) / 20.0
            base *= max(drawdown_factor, 0.25)

        # Scale down if losing streak
        recent_losses = self._recent_consecutive_losses()
        if recent_losses >= 2:
            streak_factor = max(1.0 - recent_losses * 0.2, 0.3)
            base *= streak_factor

        # Scale up slightly if on winning streak (max 1.5x)
        recent_wins = self._recent_consecutive_wins()
        if recent_wins >= 3:
            base *= min(1.0 + recent_wins * 0.1, 1.5)

        return round(min(base, self.MAX_POSITION_SIZE_PCT), 2)

    def record_trade_entry(
        self,
        symbol: str,
        action: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        position_size_pct: float,
        confidence_pct: float,
    ) -> TradeRecord:
        """Record a new trade entry."""
        trade = TradeRecord(
            trade_id=f"T{self.state.total_trades + 1:04d}",
            timestamp=datetime.utcnow().isoformat(),
            symbol=symbol,
            action=action,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_pct=position_size_pct,
            confidence_pct=confidence_pct,
        )
        self.trades.append(trade)
        self.state.total_trades += 1
        self.state.daily_trades += 1
        self.state.open_positions += 1
        self._save_journal()
        return trade

    def record_trade_exit(self, trade_id: str, exit_price: float, reason: str = "target") -> Optional[TradeRecord]:
        """Record a trade exit and update P&L."""
        trade = next((t for t in self.trades if t.trade_id == trade_id and t.status == "OPEN"), None)
        if not trade:
            return None

        trade.exit_price = exit_price
        trade.exit_timestamp = datetime.utcnow().isoformat()

        # Calculate P&L
        if trade.action == "BUY":
            trade.pnl = (exit_price - trade.entry_price) * (self.state.capital * trade.position_size_pct / 100) / trade.entry_price
        else:
            trade.pnl = (trade.entry_price - exit_price) * (self.state.capital * trade.position_size_pct / 100) / trade.entry_price

        trade.pnl_pct = trade.pnl / self.state.capital * 100
        trade.status = "STOPPED_OUT" if reason == "stop_loss" else "CLOSED"

        # Update state
        self.state.current_capital += trade.pnl
        self.state.daily_pnl += trade.pnl
        self.state.open_positions = max(0, self.state.open_positions - 1)

        if trade.pnl >= 0:
            self.state.winning_trades += 1
        else:
            self.state.losing_trades += 1
            self._last_loss_time = datetime.utcnow()

        if self.state.current_capital > self.state.max_capital:
            self.state.max_capital = self.state.current_capital

        self._update_drawdown()
        self._save_journal()
        return trade

    def get_performance_stats(self) -> dict:
        """Get comprehensive performance statistics."""
        closed = [t for t in self.trades if t.status != "OPEN"]
        if not closed:
            return {"message": "No closed trades yet"}

        wins = [t for t in closed if t.pnl and t.pnl > 0]
        losses = [t for t in closed if t.pnl and t.pnl < 0]

        total_pnl = sum(t.pnl for t in closed if t.pnl)
        win_rate = len(wins) / len(closed) * 100 if closed else 0

        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0
        profit_factor = abs(sum(t.pnl for t in wins)) / abs(sum(t.pnl for t in losses)) if losses and sum(t.pnl for t in losses) != 0 else float("inf")

        return {
            "total_trades": len(closed),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl / self.state.capital * 100, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(self.state.max_drawdown_pct, 2),
            "current_capital": round(self.state.current_capital, 2),
        }

    def _update_drawdown(self):
        dd = (self.state.max_capital - self.state.current_capital) / self.state.max_capital * 100
        self.state.current_drawdown_pct = max(dd, 0)
        self.state.max_drawdown_pct = max(self.state.max_drawdown_pct, self.state.current_drawdown_pct)

    def _recent_consecutive_losses(self) -> int:
        count = 0
        for t in reversed(self.trades):
            if t.status == "OPEN":
                continue
            if t.pnl and t.pnl < 0:
                count += 1
            else:
                break
        return count

    def _recent_consecutive_wins(self) -> int:
        count = 0
        for t in reversed(self.trades):
            if t.status == "OPEN":
                continue
            if t.pnl and t.pnl > 0:
                count += 1
            else:
                break
        return count

    def _save_journal(self):
        try:
            data = {
                "state": asdict(self.state),
                "trades": [asdict(t) for t in self.trades[-500:]],  # Keep last 500
            }
            self.journal_path.write_text(json.dumps(data, indent=2, default=str))
        except Exception as e:
            logger.error(f"Failed to save journal: {e}")

    def _load_journal(self):
        if not self.journal_path.exists():
            return
        try:
            data = json.loads(self.journal_path.read_text())
            state_data = data.get("state", {})
            for key, val in state_data.items():
                if hasattr(self.state, key):
                    setattr(self.state, key, val)
            self.trades = [TradeRecord(**t) for t in data.get("trades", [])]
            logger.info(f"Loaded {len(self.trades)} trades from journal")
        except Exception as e:
            logger.warning(f"Could not load journal: {e}")

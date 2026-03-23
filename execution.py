from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Position:
    side: str  # BUY means long, SELL means short
    entry_price: float
    size: float
    stop_loss_pct: float
    entry_step: int


@dataclass
class Trade:
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    entry_step: int
    exit_step: int
    exit_reason: str


@dataclass
class StepReport:
    opened_position: Optional[Position]
    closed_trade: Optional[Trade]
    equity: float
    unrealized_pnl: float
    total_pnl: float


class ExecutionEngine:
    """Tracks portfolio state and simulates fills with slippage."""

    def __init__(
        self,
        initial_capital: float = 10_000.0,
        slippage_bps: float = 9.0,
        seed: int = 19,
        take_profit_pct: float = 0.07,
        max_hold_steps: int = 24,
    ) -> None:
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.slippage_bps = slippage_bps
        self.take_profit_pct = take_profit_pct
        self.max_hold_steps = max_hold_steps
        self.rng = random.Random(seed)

        self.position: Optional[Position] = None
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [initial_capital]

    def _fill_price(self, market_price: float, order_side: str) -> float:
        slippage = (self.slippage_bps / 10_000.0) * (1.0 + self.rng.random())
        if order_side == "BUY":
            return market_price * (1.0 + slippage)
        return market_price * (1.0 - slippage)

    def _unrealized_pnl(self, market_price: float) -> float:
        if self.position is None:
            return 0.0

        if self.position.side == "BUY":
            return (market_price - self.position.entry_price) * self.position.size
        return (self.position.entry_price - market_price) * self.position.size

    def _close_position(self, market_price: float, step: int, reason: str) -> Trade:
        assert self.position is not None
        pos = self.position

        # Closing long requires SELL; closing short requires BUY.
        exit_order_side = "SELL" if pos.side == "BUY" else "BUY"
        exit_price = self._fill_price(market_price, exit_order_side)

        if pos.side == "BUY":
            pnl = (exit_price - pos.entry_price) * pos.size
        else:
            pnl = (pos.entry_price - exit_price) * pos.size

        self.capital += pnl

        trade = Trade(
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            size=pos.size,
            pnl=pnl,
            entry_step=pos.entry_step,
            exit_step=step,
            exit_reason=reason,
        )
        self.trades.append(trade)
        self.position = None
        return trade

    def process_step(
        self,
        step: int,
        market_price: float,
        action: str,
        requested_size: float,
        stop_loss_pct: float,
    ) -> StepReport:
        opened_position: Optional[Position] = None
        closed_trade: Optional[Trade] = None

        # 1) Manage open position (stop loss / signal flip).
        if self.position is not None:
            pos = self.position
            if pos.side == "BUY":
                loss_pct = (pos.entry_price - market_price) / max(pos.entry_price, 1e-9)
                gain_pct = (market_price - pos.entry_price) / max(pos.entry_price, 1e-9)
                opposite_signal = action == "SELL"
            else:
                loss_pct = (market_price - pos.entry_price) / max(pos.entry_price, 1e-9)
                gain_pct = (pos.entry_price - market_price) / max(pos.entry_price, 1e-9)
                opposite_signal = action == "BUY"

            held_steps = step - pos.entry_step

            if loss_pct >= pos.stop_loss_pct:
                closed_trade = self._close_position(market_price, step, "stop_loss")
            elif gain_pct >= self.take_profit_pct:
                closed_trade = self._close_position(market_price, step, "take_profit")
            elif held_steps >= self.max_hold_steps:
                closed_trade = self._close_position(market_price, step, "time_exit")
            elif opposite_signal:
                closed_trade = self._close_position(market_price, step, "signal_flip")

        # 2) Open new position if we are flat and have a trade signal.
        if self.position is None and action in {"BUY", "SELL"} and requested_size > 0:
            entry_price = self._fill_price(market_price, action)
            self.position = Position(
                side=action,
                entry_price=entry_price,
                size=requested_size,
                stop_loss_pct=stop_loss_pct,
                entry_step=step,
            )
            opened_position = self.position

        unrealized = self._unrealized_pnl(market_price)
        equity = self.capital + unrealized
        total_pnl = equity - self.initial_capital
        self.equity_curve.append(equity)

        return StepReport(
            opened_position=opened_position,
            closed_trade=closed_trade,
            equity=equity,
            unrealized_pnl=unrealized,
            total_pnl=total_pnl,
        )

    def close_end_of_run(self, market_price: float, final_step: int) -> Optional[Trade]:
        if self.position is None:
            return None
        trade = self._close_position(market_price, final_step, "end_of_run")
        equity = self.capital
        self.equity_curve.append(equity)
        return trade

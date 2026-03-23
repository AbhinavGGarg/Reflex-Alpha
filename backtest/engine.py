from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

from execution import ExecutionEngine
from metrics import compute_metrics
from models import BacktestResult, MarketDataPoint, OpenPosition, Trade
from risk import RiskEngine
from signals import SignalEngine
from strategy import StrategyEngine


@dataclass
class BacktestConfig:
    initial_capital: float = 10_000.0
    max_hold_steps: int = 28
    take_profit_pct: float = 0.085


class ReflexAlphaEngine:
    def __init__(
        self,
        signal_engine: SignalEngine,
        strategy_engine: StrategyEngine,
        execution_engine: ExecutionEngine,
        risk_engine: RiskEngine,
        config: BacktestConfig | None = None,
    ) -> None:
        self.signal_engine = signal_engine
        self.strategy_engine = strategy_engine
        self.execution_engine = execution_engine
        self.risk_engine = risk_engine
        self.config = config or BacktestConfig()
        self.reset()

    def reset(self) -> None:
        self.capital = self.config.initial_capital
        self.peak_equity = self.config.initial_capital
        self.open_position: OpenPosition | None = None
        self.trade_counter = 0
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.decisions: List[str] = []
        self.adaptation_events: List[str] = []
        self.halted = False

    @staticmethod
    def _side_multiplier(side: str) -> float:
        return 1.0 if side == "BUY" else -1.0

    def _mark_to_market(self, current_price: float) -> float:
        if not self.open_position:
            return self.capital

        position = self.open_position
        side_mult = self._side_multiplier(position.side)
        unrealized = side_mult * (current_price - position.entry_price) * position.size
        return self.capital + unrealized

    def _open_trade(self, side: str, confidence: float, volatility: float, market_data: List[MarketDataPoint], index: int, verbose: bool) -> None:
        if self.open_position is not None or self.halted:
            return

        current_price = market_data[index].price
        size = self.risk_engine.position_size(
            confidence_score=confidence,
            volatility=max(volatility, 0.005),
            capital=self.capital,
            price=current_price,
        )
        if size <= 0:
            return

        entry_price, fill_index, _, _ = self.execution_engine.simulate_fill(
            side=side,
            requested_price=current_price,
            market_data=market_data,
            index=index,
        )

        self.open_position = OpenPosition(
            side=side,
            entry_price=entry_price,
            size=size,
            entry_index=fill_index,
            confidence=confidence,
            stop_loss_pct=self.risk_engine.stop_loss_pct(volatility),
        )

        if verbose:
            print(f"[TRADE] {side} @ {entry_price:.2f} | size: {size:.0f}")

    def _close_trade(self, market_data: List[MarketDataPoint], index: int, reason: str, verbose: bool) -> None:
        if self.open_position is None:
            return

        position = self.open_position
        current_price = market_data[index].price
        exit_side = "SELL" if position.side == "BUY" else "BUY"

        exit_price, fill_index, _, _ = self.execution_engine.simulate_fill(
            side=exit_side,
            requested_price=current_price,
            market_data=market_data,
            index=index,
        )

        if position.side == "BUY":
            pnl = (exit_price - position.entry_price) * position.size
        else:
            pnl = (position.entry_price - exit_price) * position.size

        self.capital += pnl
        self.trade_counter += 1

        trade = Trade(
            trade_id=self.trade_counter,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=exit_price,
            size=position.size,
            entry_index=position.entry_index,
            exit_index=fill_index,
            pnl=pnl,
            confidence=position.confidence,
            exit_reason=reason,
        )
        self.trades.append(trade)

        adapt_message = self.risk_engine.update_adaptive_risk(pnl)
        if adapt_message:
            self.adaptation_events.append(adapt_message)
            if verbose:
                print(f"[ADAPT] {adapt_message}")

        if verbose:
            print(f"[TRADE] {exit_side} @ {exit_price:.2f} | PnL: {pnl:+.2f}")

        self.open_position = None

    def _process_tick(self, market_data: List[MarketDataPoint], index: int, verbose: bool, live_trace: bool) -> None:
        if self.halted:
            return

        point = market_data[index]
        signals = self.signal_engine.compute(market_data, index)
        confidence = self.strategy_engine.confidence_score(signals)
        action = self.strategy_engine.action(confidence)
        self.decisions.append(action)

        current_equity = self._mark_to_market(point.price)
        self.peak_equity = max(self.peak_equity, current_equity)
        self.equity_curve.append(current_equity)

        if not self.risk_engine.check_drawdown(current_equity, self.peak_equity):
            self._close_trade(market_data, index, "max_drawdown", verbose)
            self.halted = True
            if verbose:
                print("[RISK] Max drawdown breached. Trading halted.")
            return

        if self.open_position:
            position = self.open_position
            side_mult = self._side_multiplier(position.side)
            move_pct = side_mult * ((point.price - position.entry_price) / max(position.entry_price, 1e-9))
            held_steps = index - position.entry_index

            should_flip = (position.side == "BUY" and action == "SELL") or (
                position.side == "SELL" and action == "BUY"
            )

            if move_pct <= -position.stop_loss_pct:
                self._close_trade(market_data, index, "stop_loss", verbose)
            elif move_pct >= self.config.take_profit_pct:
                self._close_trade(market_data, index, "take_profit", verbose)
            elif held_steps >= self.config.max_hold_steps:
                self._close_trade(market_data, index, "time_exit", verbose)
            elif should_flip and abs(confidence) > self.strategy_engine.config.buy_threshold:
                self._close_trade(market_data, index, "signal_flip", verbose)

        if self.open_position is None and action in {"BUY", "SELL"}:
            self._open_trade(
                side=action,
                confidence=confidence,
                volatility=signals["raw_volatility"],
                market_data=market_data,
                index=index,
                verbose=verbose,
            )

        if live_trace and verbose:
            print(
                f"[LIVE] {action} @ {point.price:.2f} | confidence: {confidence:+.2f} "
                f"| risk x{self.risk_engine.risk_multiplier:.2f}"
            )

    def run_backtest(self, market_data: List[MarketDataPoint], verbose: bool = True) -> BacktestResult:
        self.reset()

        for index in range(len(market_data)):
            self._process_tick(market_data=market_data, index=index, verbose=verbose, live_trace=False)

        if self.open_position:
            self._close_trade(market_data, len(market_data) - 1, "end_of_backtest", verbose)

        performance = compute_metrics(self.trades, self.equity_curve, self.config.initial_capital)

        return BacktestResult(
            trades=self.trades,
            equity_curve=self.equity_curve,
            decisions=self.decisions,
            adaptation_events=self.adaptation_events,
            metrics=performance.as_dict(),
        )

    def run_live_simulation(
        self,
        stream,
        warmup_points: int = 60,
        iterations: int = 80,
        refresh_seconds: float = 0.3,
        verbose: bool = True,
    ) -> BacktestResult:
        self.reset()

        # Warmup provides enough context for momentum/volatility signals.
        # We do not place trades during warmup; trading starts with live ticks.
        history = stream.bootstrap(warmup_points)

        for _ in range(iterations):
            history.append(stream.fetch_next())
            self._process_tick(
                market_data=history,
                index=len(history) - 1,
                verbose=verbose,
                live_trace=True,
            )

            if self.halted:
                break

            if refresh_seconds > 0:
                time.sleep(refresh_seconds)

        if self.open_position:
            self._close_trade(history, len(history) - 1, "end_of_live", verbose)

        performance = compute_metrics(self.trades, self.equity_curve, self.config.initial_capital)

        return BacktestResult(
            trades=self.trades,
            equity_curve=self.equity_curve,
            decisions=self.decisions,
            adaptation_events=self.adaptation_events,
            metrics=performance.as_dict(),
        )

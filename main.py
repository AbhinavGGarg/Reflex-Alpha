from __future__ import annotations

import argparse
import math
import time
from statistics import mean, pstdev

from execution import ExecutionEngine
from market import MarketSimulator
from risk import RiskManager
from signals import SignalEngine
from strategy import StrategyEngine


def max_drawdown(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst


def sharpe_ratio(trade_returns: list[float]) -> float:
    if len(trade_returns) < 2:
        return 0.0
    std = pstdev(trade_returns)
    if std == 0:
        return 0.0
    return (mean(trade_returns) / std) * math.sqrt(len(trade_returns))


def run_simulation(steps: int, delay: float, seed: int, initial_capital: float) -> None:
    market = MarketSimulator(seed=seed)
    signal_engine = SignalEngine(seed=seed + 101)
    strategy_engine = StrategyEngine(entry_threshold=0.55)
    risk_manager = RiskManager()
    execution_engine = ExecutionEngine(initial_capital=initial_capital, seed=seed + 211)

    print("Starting Reflex Alpha local trading simulation...")
    print(f"Steps: {steps} | Delay: {delay}s | Initial Capital: {initial_capital:.2f}")
    print("-" * 56)

    last_price = 0.50

    for t in range(steps):
        tick = market.step(t)
        last_price = tick.price

        signal = signal_engine.update(price=tick.price)
        decision = strategy_engine.decide(signal.confidence)

        requested_size = 0.0
        if decision.action in {"BUY", "SELL"} and execution_engine.position is None:
            requested_size = risk_manager.position_size(
                capital=execution_engine.capital,
                price=tick.price,
                confidence=signal.confidence,
                raw_volatility=signal.raw_volatility,
            )

        report = execution_engine.process_step(
            step=t,
            market_price=tick.price,
            action=decision.action,
            requested_size=requested_size,
            stop_loss_pct=risk_manager.stop_loss_pct(signal.raw_volatility),
        )

        print(f"[TIME {t}]")
        print(f"Price: {tick.price:.2f}")
        print(f"Signal: {decision.action} (confidence: {decision.confidence:+.2f})")

        active_size = execution_engine.position.size if execution_engine.position else 0.0
        print(f"Position Size: {active_size:.0f}")
        print(f"PnL: {report.total_pnl:+.2f}")
        print(f"Capital: {report.equity:.2f}")

        if report.opened_position is not None:
            side = report.opened_position.side
            print(
                f"[TRADE] Open {side} @ {report.opened_position.entry_price:.3f} | "
                f"size: {report.opened_position.size:.0f}"
            )

        if report.closed_trade is not None:
            closed = report.closed_trade
            close_side = "SELL" if closed.side == "BUY" else "BUY"
            print(
                f"[TRADE] Close {close_side} @ {closed.exit_price:.3f} | "
                f"PnL: {closed.pnl:+.2f} | reason: {closed.exit_reason}"
            )
            for message in risk_manager.on_trade_closed(closed.pnl):
                print(f"[ADAPT] {message}")

        print()
        time.sleep(delay)

    # Close any remaining open position at the end.
    final_trade = execution_engine.close_end_of_run(last_price, steps)
    if final_trade is not None:
        print(
            f"[TRADE] Final close {'SELL' if final_trade.side == 'BUY' else 'BUY'} @ "
            f"{final_trade.exit_price:.3f} | PnL: {final_trade.pnl:+.2f}"
        )
        for message in risk_manager.on_trade_closed(final_trade.pnl):
            print(f"[ADAPT] {message}")
        print()

    total_pnl = execution_engine.capital - initial_capital
    total_trades = len(execution_engine.trades)
    wins = sum(1 for trade in execution_engine.trades if trade.pnl > 0)
    win_rate = (wins / total_trades * 100.0) if total_trades else 0.0

    trade_returns = [
        trade.pnl / max(trade.entry_price * trade.size, 1e-9)
        for trade in execution_engine.trades
    ]

    print("==== FINAL RESULTS ====")
    print(f"Total PnL: {total_pnl:+.2f}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Sharpe Ratio: {sharpe_ratio(trade_returns):.2f}")
    print(f"Max Drawdown: {-max_drawdown(execution_engine.equity_curve) * 100:.2f}%")
    print(f"Total Trades: {total_trades}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reflex Alpha local trading simulation")
    parser.add_argument("--steps", type=int, default=200, help="Number of simulation steps")
    parser.add_argument("--delay", type=float, default=0.10, help="Delay in seconds per step")
    parser.add_argument("--seed", type=int, default=7, help="Random seed")
    parser.add_argument("--capital", type=float, default=10_000.0, help="Initial capital")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_simulation(steps=args.steps, delay=args.delay, seed=args.seed, initial_capital=args.capital)


if __name__ == "__main__":
    main()

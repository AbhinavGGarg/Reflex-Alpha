from __future__ import annotations

import argparse

from backtest import BacktestConfig, ReflexAlphaEngine
from data import MarketDataStream, get_market_data
from execution import ExecutionConfig, ExecutionEngine
from metrics import PerformanceMetrics, print_metrics
from risk import RiskConfig, RiskEngine
from signals import SignalConfig, SignalEngine
from strategy import StrategyConfig, StrategyEngine


def _build_engine(seed: int, initial_capital: float) -> ReflexAlphaEngine:
    signal_engine = SignalEngine(SignalConfig())
    strategy_engine = StrategyEngine(StrategyConfig())
    execution_engine = ExecutionEngine(ExecutionConfig(random_seed=seed + 17))
    risk_engine = RiskEngine(RiskConfig())
    backtest_config = BacktestConfig(initial_capital=initial_capital)

    return ReflexAlphaEngine(
        signal_engine=signal_engine,
        strategy_engine=strategy_engine,
        execution_engine=execution_engine,
        risk_engine=risk_engine,
        config=backtest_config,
    )


def _metrics_from_dict(raw: dict) -> PerformanceMetrics:
    return PerformanceMetrics(
        total_pnl=float(raw["total_pnl"]),
        win_rate=float(raw["win_rate"]),
        sharpe_ratio=float(raw["sharpe_ratio"]),
        max_drawdown=float(raw["max_drawdown"]),
        number_of_trades=int(raw["number_of_trades"]),
    )


def run_backtest(args: argparse.Namespace) -> None:
    print("=== Reflex Alpha | Backtest ===")

    market_data = get_market_data(
        num_points=args.points,
        market_id=args.market_id,
        use_real_api=args.real_api,
        seed=args.seed,
    )

    engine = _build_engine(seed=args.seed, initial_capital=args.capital)
    result = engine.run_backtest(market_data, verbose=not args.quiet)
    metrics = _metrics_from_dict(result.metrics)

    print_metrics(metrics)


def run_live_simulation(args: argparse.Namespace) -> None:
    print("=== Reflex Alpha | Live Simulation ===")

    stream = MarketDataStream(
        seed=args.seed + 101,
        market_id=args.market_id,
        use_real_api=args.real_api,
        start_price=0.50,
    )

    engine = _build_engine(seed=args.seed + 211, initial_capital=args.capital)
    result = engine.run_live_simulation(
        stream=stream,
        warmup_points=args.warmup,
        iterations=args.live_steps,
        refresh_seconds=args.refresh,
        verbose=True,
    )
    metrics = _metrics_from_dict(result.metrics)

    print_metrics(metrics)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reflex Alpha: adaptive Polymarket trading simulator")
    parser.add_argument("--mode", choices=["backtest", "live", "both"], default="backtest")
    parser.add_argument("--points", type=int, default=420, help="Backtest data points")
    parser.add_argument("--live-steps", type=int, default=40, help="Live simulation iterations")
    parser.add_argument("--warmup", type=int, default=60, help="Warmup ticks before live mode")
    parser.add_argument("--refresh", type=float, default=0.15, help="Seconds between live ticks")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--capital", type=float, default=10_000.0)
    parser.add_argument("--market-id", type=str, default=None, help="Optional Polymarket market id")
    parser.add_argument("--real-api", action="store_true", help="Try blending live Polymarket snapshots")
    parser.add_argument("--quiet", action="store_true", help="Reduce per-trade logging in backtest mode")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode in {"backtest", "both"}:
        run_backtest(args)

    if args.mode in {"live", "both"}:
        run_live_simulation(args)


if __name__ == "__main__":
    main()

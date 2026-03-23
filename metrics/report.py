from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from statistics import mean, pstdev
from typing import Dict, List

from models import Trade


@dataclass
class PerformanceMetrics:
    total_pnl: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    number_of_trades: int

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


def _max_drawdown(equity_curve: List[float]) -> float:
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0

    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)

    return max_dd


def compute_metrics(trades: List[Trade], equity_curve: List[float], initial_capital: float) -> PerformanceMetrics:
    total_pnl = sum(trade.pnl for trade in trades)
    wins = sum(1 for trade in trades if trade.pnl > 0)
    win_rate = (wins / len(trades) * 100.0) if trades else 0.0

    # Simplified trade-based Sharpe ratio.
    trade_returns = []
    for trade in trades:
        notional = max(trade.entry_price * trade.size, 1e-9)
        trade_returns.append(trade.pnl / notional)

    if len(trade_returns) > 1 and pstdev(trade_returns) > 0:
        sharpe_ratio = (mean(trade_returns) / pstdev(trade_returns)) * sqrt(len(trade_returns))
    else:
        sharpe_ratio = 0.0

    max_drawdown = _max_drawdown(equity_curve)

    return PerformanceMetrics(
        total_pnl=total_pnl,
        win_rate=win_rate,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        number_of_trades=len(trades),
    )


def print_metrics(metrics: PerformanceMetrics) -> None:
    print("[METRICS]")
    print(f"PnL: {metrics.total_pnl:+.2f}")
    print(f"Win Rate: {metrics.win_rate:.2f}%")
    print(f"Sharpe: {metrics.sharpe_ratio:.2f}")
    print(f"Max DD: {-metrics.max_drawdown * 100.0:.2f}%")
    print(f"Trades: {metrics.number_of_trades}")

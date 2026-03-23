from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from backtest import BacktestConfig, ReflexAlphaEngine
from data import MarketDataStream, get_market_data
from execution import ExecutionConfig, ExecutionEngine
from risk import RiskConfig, RiskEngine
from signals import SignalConfig, SignalEngine
from strategy import StrategyConfig, StrategyEngine


def json_response(handler, status_code: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def parse_query(path: str) -> Dict[str, str]:
    parsed = urlparse(path)
    raw = parse_qs(parsed.query)
    return {key: values[-1] for key, values in raw.items() if values}


def as_int(raw: Dict[str, str], key: str, default: int, low: int, high: int) -> int:
    value = int(raw.get(key, default))
    if value < low or value > high:
        raise ValueError(f"{key} must be between {low} and {high}")
    return value


def as_float(raw: Dict[str, str], key: str, default: float, low: float, high: float) -> float:
    value = float(raw.get(key, default))
    if value < low or value > high:
        raise ValueError(f"{key} must be between {low} and {high}")
    return value


def as_bool(raw: Dict[str, str], key: str, default: bool = False) -> bool:
    if key not in raw:
        return default
    return raw[key].lower() in {"1", "true", "yes", "y", "on"}


def build_engine(seed: int, capital: float) -> ReflexAlphaEngine:
    return ReflexAlphaEngine(
        signal_engine=SignalEngine(SignalConfig()),
        strategy_engine=StrategyEngine(StrategyConfig()),
        execution_engine=ExecutionEngine(ExecutionConfig(random_seed=seed + 17)),
        risk_engine=RiskEngine(RiskConfig()),
        config=BacktestConfig(initial_capital=capital),
    )


def result_payload(result) -> Dict[str, Any]:
    recent_trades = [
        {
            "id": t.trade_id,
            "side": t.side,
            "entry": round(t.entry_price, 4),
            "exit": round(t.exit_price, 4),
            "size": round(t.size, 3),
            "pnl": round(t.pnl, 4),
            "reason": t.exit_reason,
        }
        for t in result.trades[-10:]
    ]

    return {
        "metrics": result.metrics,
        "trade_count": len(result.trades),
        "adaptation_events": result.adaptation_events,
        "recent_trades": recent_trades,
    }


def run_backtest_payload(points: int, seed: int, capital: float, real_api: bool) -> Dict[str, Any]:
    market_data = get_market_data(num_points=points, seed=seed, use_real_api=real_api)
    engine = build_engine(seed=seed, capital=capital)
    result = engine.run_backtest(market_data=market_data, verbose=False)
    return {
        "mode": "backtest",
        "points": points,
        "seed": seed,
        "capital": capital,
        **result_payload(result),
    }


def run_live_payload(live_steps: int, warmup: int, seed: int, capital: float, real_api: bool) -> Dict[str, Any]:
    stream = MarketDataStream(
        seed=seed + 101,
        market_id=None,
        use_real_api=real_api,
        start_price=0.50,
    )
    engine = build_engine(seed=seed + 211, capital=capital)
    result = engine.run_live_simulation(
        stream=stream,
        warmup_points=warmup,
        iterations=live_steps,
        refresh_seconds=0.0,
        verbose=False,
    )
    return {
        "mode": "live-simulation",
        "live_steps": live_steps,
        "warmup": warmup,
        "seed": seed,
        "capital": capital,
        **result_payload(result),
    }

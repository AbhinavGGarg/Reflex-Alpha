from __future__ import annotations

import math
import time
from dataclasses import dataclass
from statistics import pstdev
from typing import Dict, List

from stock_connector import StockDataClient, parse_symbols


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class StockSignal:
    symbol: str
    price: float
    momentum_score: float
    volatility_penalty: float
    smart_flow_score: float
    confidence: float
    action: str
    suggested_dollars: float


class StockSignalEngine:
    """Ranks stocks using momentum + volatility + flow style scoring."""

    def score(self, symbol: str, closes: List[float], volumes: List[float], capital: float) -> StockSignal:
        price = closes[-1]

        momentum_raw = 0.0
        if len(closes) >= 6:
            momentum_raw = (closes[-1] - closes[-6]) / max(closes[-6], 1e-9)
        momentum_score = _clamp(momentum_raw / 0.03, -2.0, 2.0)

        returns = []
        for idx in range(1, min(len(closes), 21)):
            prev = closes[-idx - 1]
            curr = closes[-idx]
            if prev > 0:
                returns.append((curr - prev) / prev)

        raw_volatility = pstdev(returns) if len(returns) > 1 else 0.0
        volatility_penalty = _clamp(raw_volatility / 0.04, 0.0, 2.0)

        avg_volume = sum(volumes[-20:-1]) / max(len(volumes[-20:-1]), 1)
        volume_ratio = volumes[-1] / max(avg_volume, 1.0)

        # Proxy for "smart flow": price trend + unusual volume confirmation.
        smart_flow_score = _clamp((volume_ratio - 1.0) * 0.9 + momentum_score * 0.3, -1.8, 1.8)

        confidence = momentum_score + smart_flow_score - volatility_penalty
        confidence = _clamp(confidence, -3.0, 3.0)

        if confidence >= 1.2:
            action = "STRONG BUY"
        elif confidence >= 0.45:
            action = "BUY"
        elif confidence <= -1.2:
            action = "STRONG SELL"
        elif confidence <= -0.45:
            action = "SELL"
        else:
            action = "WATCH"

        # Simple risk-adjusted sizing guidance.
        base_fraction = 0.02 + abs(confidence) * 0.02
        adjusted_fraction = base_fraction / (1.0 + volatility_penalty)
        adjusted_fraction = _clamp(adjusted_fraction, 0.01, 0.12)

        if action in {"SELL", "STRONG SELL", "WATCH"}:
            suggested_dollars = 0.0
        else:
            suggested_dollars = capital * adjusted_fraction

        return StockSignal(
            symbol=symbol,
            price=price,
            momentum_score=momentum_score,
            volatility_penalty=volatility_penalty,
            smart_flow_score=smart_flow_score,
            confidence=confidence,
            action=action,
            suggested_dollars=suggested_dollars,
        )


def run_stock_terminal(
    symbols_raw: str,
    cycles: int,
    refresh_seconds: float,
    scanner_capital: float,
) -> None:
    symbols = parse_symbols(symbols_raw)
    if not symbols:
        raise ValueError("No symbols provided. Example: --symbols AAPL,MSFT,NVDA")

    client = StockDataClient()
    signal_engine = StockSignalEngine()

    histories: Dict[str, tuple[List[float], List[float]]] = {}

    print("Starting live stock scanner mode...")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Cycles: {cycles} | Refresh: {refresh_seconds}s | Reference Capital: {scanner_capital:.2f}")
    print("=" * 74)

    # Initial history load.
    for symbol in symbols:
        try:
            history = client.fetch_history(symbol)
            histories[symbol] = (history.closes, history.volumes)
        except Exception as exc:
            print(f"[WARN] Could not load history for {symbol}: {exc}")

    if not histories:
        raise RuntimeError("No valid symbols with usable history data.")

    for cycle in range(cycles):
        print(f"\n[CYCLE {cycle + 1}/{cycles}]")

        cycle_signals: List[StockSignal] = []

        for symbol in symbols:
            if symbol not in histories:
                continue

            closes, volumes = histories[symbol]

            try:
                quote = client.fetch_quote(symbol)
            except Exception as exc:
                print(f"{symbol:<8} | quote error: {exc}")
                continue

            # Keep rolling history fresh with current quote snapshot.
            closes = closes[-119:] + [quote.close_price]
            volumes = volumes[-119:] + [quote.volume]
            histories[symbol] = (closes, volumes)

            signal = signal_engine.score(
                symbol=symbol,
                closes=closes,
                volumes=volumes,
                capital=scanner_capital,
            )
            cycle_signals.append(signal)

        if not cycle_signals:
            print("No signal data for this cycle.")
            time.sleep(refresh_seconds)
            continue

        cycle_signals.sort(key=lambda item: item.confidence, reverse=True)

        for sig in cycle_signals:
            print(
                f"{sig.symbol:<8} | ${sig.price:>8.2f} | {sig.action:<11} | "
                f"conf {sig.confidence:+.2f} | suggested ${sig.suggested_dollars:>8.0f}"
            )

        best = cycle_signals[0]
        print(
            f"Top candidate: {best.symbol} | action: {best.action} | "
            f"confidence: {best.confidence:+.2f}"
        )
        print("Note: Signals are educational, not financial advice.")

        if cycle < cycles - 1:
            time.sleep(refresh_seconds)

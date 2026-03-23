from __future__ import annotations

from dataclasses import dataclass
from statistics import pstdev
from typing import Dict, List

from models import MarketDataPoint


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class SignalConfig:
    momentum_window: int = 6
    volatility_window: int = 14
    momentum_trigger: float = 0.05


class SignalEngine:
    def __init__(self, config: SignalConfig | None = None) -> None:
        self.config = config or SignalConfig()

    def _compute_momentum(self, prices: List[float]) -> tuple[float, float]:
        if len(prices) <= self.config.momentum_window:
            return 0.0, 0.0

        reference_price = prices[-(self.config.momentum_window + 1)]
        if reference_price <= 0:
            return 0.0, 0.0

        pct_change = (prices[-1] - reference_price) / reference_price
        score = _clamp(pct_change / self.config.momentum_trigger, -2.0, 2.0)
        return score, pct_change

    def _compute_volatility(self, prices: List[float]) -> tuple[float, float]:
        if len(prices) <= 2:
            return 0.0, 0.0

        lookback_prices = prices[-self.config.volatility_window :]
        returns = []
        for idx in range(1, len(lookback_prices)):
            prev = lookback_prices[idx - 1]
            curr = lookback_prices[idx]
            if prev > 0:
                returns.append((curr - prev) / prev)

        if len(returns) <= 1:
            return 0.0, 0.0

        raw_volatility = pstdev(returns)
        normalized = _clamp(raw_volatility / 0.03, 0.0, 2.0)
        return normalized, raw_volatility

    def _compute_wallet_signal(self, point: MarketDataPoint) -> float:
        flow = point.wallet_flow
        smart_total = flow.smart_buy + flow.smart_sell
        noise_total = flow.noise_buy + flow.noise_sell

        if smart_total <= 0:
            return 0.0

        smart_net = (flow.smart_buy - flow.smart_sell) / smart_total
        noise_pressure = 0.0
        if noise_total > 0:
            noise_pressure = abs(flow.noise_buy - flow.noise_sell) / noise_total

        # Reward clustered smart accumulation and discount noisy activity.
        signal = smart_net * (1.0 - noise_pressure * 0.35)
        return _clamp(signal, -1.5, 1.5)

    def compute(self, market_data: List[MarketDataPoint], index: int) -> Dict[str, float]:
        window = market_data[: index + 1]
        prices = [point.price for point in window]
        current = window[-1]

        momentum_score, momentum_change = self._compute_momentum(prices)
        volatility_score, raw_volatility = self._compute_volatility(prices)
        wallet_signal = self._compute_wallet_signal(current)
        orderbook_signal = _clamp(current.orderbook_imbalance, -1.0, 1.0)

        return {
            "momentum": momentum_score,
            "momentum_change": momentum_change,
            "volatility": volatility_score,
            "raw_volatility": raw_volatility,
            "wallet_signal": wallet_signal,
            "orderbook_signal": orderbook_signal,
        }

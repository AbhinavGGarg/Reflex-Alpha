from __future__ import annotations

import random
from dataclasses import dataclass
from statistics import pstdev
from typing import List


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class Wallet:
    wallet_id: str
    win_rate: float
    avg_size: float


@dataclass
class SignalSnapshot:
    momentum_score: float
    volatility_penalty: float
    raw_volatility: float
    wallet_score: float
    confidence: float
    smart_wallet_flow: float


class SignalEngine:
    """Builds momentum, volatility, and smart-wallet signals."""

    def __init__(self, seed: int = 31, momentum_window: int = 8, volatility_window: int = 20) -> None:
        self.rng = random.Random(seed)
        self.momentum_window = momentum_window
        self.volatility_window = volatility_window
        self.prices: List[float] = []

        # Five smart wallets with different skill profiles.
        self.wallets = [
            Wallet("wallet_alpha", 0.74, 120.0),
            Wallet("wallet_beta", 0.69, 95.0),
            Wallet("wallet_gamma", 0.66, 110.0),
            Wallet("wallet_delta", 0.63, 80.0),
            Wallet("wallet_sigma", 0.60, 70.0),
        ]

    def _momentum_score(self) -> float:
        if len(self.prices) <= self.momentum_window:
            return 0.0

        reference = self.prices[-(self.momentum_window + 1)]
        if reference <= 0:
            return 0.0

        pct_change = (self.prices[-1] - reference) / reference
        return _clamp(pct_change / 0.03, -1.6, 1.6)

    def _volatility(self) -> tuple[float, float]:
        if len(self.prices) < 3:
            return 0.0, 0.0

        lookback = self.prices[-self.volatility_window :]
        returns: List[float] = []

        for idx in range(1, len(lookback)):
            prev = lookback[idx - 1]
            curr = lookback[idx]
            if prev > 0:
                returns.append((curr - prev) / prev)

        if len(returns) < 2:
            return 0.0, 0.0

        raw_vol = pstdev(returns)
        vol_penalty = _clamp(raw_vol / 0.02, 0.0, 1.8)
        return vol_penalty, raw_vol

    def _wallet_score(self, momentum_score: float) -> tuple[float, float]:
        if not self.wallets:
            return 0.0, 0.0

        smart_buy = 0.0
        smart_sell = 0.0

        expected_direction = 1 if momentum_score >= 0 else -1
        if abs(momentum_score) < 0.05:
            expected_direction = 1 if self.rng.random() > 0.5 else -1

        for wallet in self.wallets:
            size = max(1.0, self.rng.gauss(wallet.avg_size, wallet.avg_size * 0.25))

            # Better wallets are more likely to align with the right direction.
            is_aligned = self.rng.random() < wallet.win_rate
            direction = expected_direction if is_aligned else -expected_direction

            if direction > 0:
                smart_buy += size
            else:
                smart_sell += size

        total = smart_buy + smart_sell
        if total <= 0:
            return 0.0, 0.0

        net_flow = smart_buy - smart_sell
        normalized = net_flow / total
        wallet_score = _clamp(normalized * 1.35, -1.5, 1.5)
        return wallet_score, net_flow

    def update(self, price: float) -> SignalSnapshot:
        self.prices.append(price)

        momentum = self._momentum_score()
        vol_penalty, raw_vol = self._volatility()
        wallet_score, net_flow = self._wallet_score(momentum)

        confidence = momentum + wallet_score - vol_penalty
        confidence = _clamp(confidence, -2.2, 2.2)

        return SignalSnapshot(
            momentum_score=momentum,
            volatility_penalty=vol_penalty,
            raw_volatility=raw_vol,
            wallet_score=wallet_score,
            confidence=confidence,
            smart_wallet_flow=net_flow,
        )

from __future__ import annotations

import random
from dataclasses import dataclass


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class MarketTick:
    """Single market snapshot for one simulated time step."""

    step: int
    price: float
    price_change: float
    trend_component: float
    noise_component: float
    jump_component: float
    volume: float
    spike_event: bool


class MarketSimulator:
    """Simulates realistic prediction market movement.

    Behavior includes:
    - trending regimes (bullish/bearish/flat)
    - random micro-noise
    - occasional sudden jumps (news events)
    """

    def __init__(self, start_price: float = 0.50, seed: int = 7) -> None:
        self.rng = random.Random(seed)
        self.price = _clamp(start_price, 0.02, 0.98)
        self.trend = 0.0
        self.regime_steps_remaining = 0
        self._roll_regime()

    def _roll_regime(self) -> None:
        self.trend = self.rng.uniform(-0.0065, 0.0065)
        self.regime_steps_remaining = self.rng.randint(16, 48)

    def step(self, t: int) -> MarketTick:
        if self.regime_steps_remaining <= 0:
            self._roll_regime()

        self.regime_steps_remaining -= 1

        noise = self.rng.gauss(0.0, 0.008)
        jump = 0.0
        spike_event = False

        # Simulated event/news shock.
        if self.rng.random() < 0.05:
            spike_event = True
            jump = self.rng.choice([-1.0, 1.0]) * self.rng.uniform(0.03, 0.11)

        price_change = self.trend + noise + jump
        self.price = _clamp(self.price + price_change, 0.02, 0.98)

        volume = 1100.0 + abs(price_change) * 65000.0 + self.rng.uniform(-120.0, 120.0)
        if spike_event:
            volume *= 1.75

        return MarketTick(
            step=t,
            price=self.price,
            price_change=price_change,
            trend_component=self.trend,
            noise_component=noise,
            jump_component=jump,
            volume=max(150.0, volume),
            spike_event=spike_event,
        )

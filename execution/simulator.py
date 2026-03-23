from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Tuple

from models import MarketDataPoint


@dataclass
class ExecutionConfig:
    slippage_bps: float = 12.0
    max_delay_steps: int = 2
    random_seed: int = 19


class ExecutionEngine:
    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self.config = config or ExecutionConfig()
        self.rng = random.Random(self.config.random_seed)

    def simulate_fill(
        self,
        side: str,
        requested_price: float,
        market_data: List[MarketDataPoint],
        index: int,
    ) -> Tuple[float, int, float, int]:
        """Simulate delayed execution and slippage against the current stream."""
        delay_steps = self.rng.randint(0, self.config.max_delay_steps)
        fill_index = min(index + delay_steps, len(market_data) - 1)
        market_price = market_data[fill_index].price

        slippage_rate = (self.config.slippage_bps / 10_000.0) * (1.0 + self.rng.random())

        if side == "BUY":
            fill_price = market_price * (1.0 + slippage_rate)
        else:
            fill_price = market_price * (1.0 - slippage_rate)

        return fill_price, fill_index, slippage_rate, delay_steps

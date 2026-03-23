from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class StrategyConfig:
    momentum_weight: float = 0.42
    wallet_weight: float = 0.38
    volatility_weight: float = 0.30
    orderbook_weight: float = 0.12
    buy_threshold: float = 0.32
    sell_threshold: float = 0.32


class StrategyEngine:
    def __init__(self, config: StrategyConfig | None = None) -> None:
        self.config = config or StrategyConfig()

    def confidence_score(self, signals: Dict[str, float]) -> float:
        # Core multi-factor confidence model.
        return (
            self.config.momentum_weight * signals["momentum"]
            + self.config.wallet_weight * signals["wallet_signal"]
            + self.config.orderbook_weight * signals.get("orderbook_signal", 0.0)
            - self.config.volatility_weight * signals["volatility"]
        )

    def action(self, confidence_score: float) -> str:
        if confidence_score > self.config.buy_threshold:
            return "BUY"
        if confidence_score < -self.config.sell_threshold:
            return "SELL"
        return "HOLD"

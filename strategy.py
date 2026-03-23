from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StrategyDecision:
    action: str
    confidence: float


class StrategyEngine:
    """Converts confidence into BUY/SELL/HOLD decisions."""

    def __init__(self, entry_threshold: float = 0.55) -> None:
        self.entry_threshold = entry_threshold

    def decide(self, confidence: float) -> StrategyDecision:
        if confidence > self.entry_threshold:
            return StrategyDecision(action="BUY", confidence=confidence)
        if confidence < -self.entry_threshold:
            return StrategyDecision(action="SELL", confidence=confidence)
        return StrategyDecision(action="HOLD", confidence=confidence)

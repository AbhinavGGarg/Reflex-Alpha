from __future__ import annotations

from dataclasses import dataclass
from typing import List


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class RiskState:
    aggressiveness: float = 1.0
    win_count: int = 0
    loss_count: int = 0
    total_trades: int = 0
    loss_streak: int = 0


class RiskManager:
    """Dynamic sizing + adaptive behavior based on performance."""

    def __init__(self) -> None:
        self.state = RiskState()
        self.max_exposure_fraction = 0.28
        self.min_aggressiveness = 0.35
        self.max_aggressiveness = 1.9
        self._last_boost_trade_count = 0

    @property
    def win_rate(self) -> float:
        if self.state.total_trades == 0:
            return 0.0
        return self.state.win_count / self.state.total_trades

    def position_size(self, capital: float, price: float, confidence: float, raw_volatility: float) -> float:
        if abs(confidence) < 0.08:
            return 0.0

        effective_vol = max(raw_volatility, 0.005)

        # Risk-aware notional sizing using confidence and inverse volatility.
        raw_notional = capital * abs(confidence) * (1.0 / effective_vol) * 0.0022
        raw_notional *= self.state.aggressiveness

        max_notional = capital * self.max_exposure_fraction
        capped_notional = min(raw_notional, max_notional)

        size = capped_notional / max(price, 0.01)
        return max(0.0, size)

    def stop_loss_pct(self, raw_volatility: float) -> float:
        dynamic_stop = 0.02 + raw_volatility * 1.6
        return _clamp(dynamic_stop, 0.015, 0.09)

    def on_trade_closed(self, pnl: float) -> List[str]:
        messages: List[str] = []
        self.state.total_trades += 1

        if pnl > 0:
            self.state.win_count += 1
            self.state.loss_streak = 0
        else:
            self.state.loss_count += 1
            self.state.loss_streak += 1

        # Adaptive defense mode after 3 consecutive losses.
        if self.state.loss_streak >= 3:
            old = self.state.aggressiveness
            self.state.aggressiveness = max(self.min_aggressiveness, self.state.aggressiveness * 0.70)
            self.state.loss_streak = 0
            messages.append(
                f"3-loss streak detected -> aggressiveness {old:.2f} to {self.state.aggressiveness:.2f}"
            )

        # Adaptive offense mode when win rate is consistently strong.
        if (
            self.state.total_trades >= 8
            and self.win_rate > 0.60
            and (self.state.total_trades - self._last_boost_trade_count) >= 4
        ):
            old = self.state.aggressiveness
            self.state.aggressiveness = min(self.max_aggressiveness, self.state.aggressiveness * 1.12)
            self._last_boost_trade_count = self.state.total_trades
            if self.state.aggressiveness > old:
                messages.append(
                    f"High win rate -> aggressiveness {old:.2f} to {self.state.aggressiveness:.2f}"
                )

        return messages

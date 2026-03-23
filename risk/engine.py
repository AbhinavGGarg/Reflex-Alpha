from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskConfig:
    base_position_size: float = 140.0
    max_position_size: float = 800.0
    max_capital_fraction: float = 0.25
    min_volatility_floor: float = 0.008
    max_drawdown_limit: float = 0.22
    base_stop_loss: float = 0.03
    loss_streak_cut_factor: float = 0.65
    min_risk_multiplier: float = 0.30
    win_rate_boost_threshold: float = 0.60
    win_rate_boost_factor: float = 1.12
    max_risk_multiplier: float = 1.85
    min_trades_for_boost: int = 8
    boost_cooldown_trades: int = 5


class RiskEngine:
    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        self.risk_multiplier = 1.0
        self.loss_streak = 0
        self.wins = 0
        self.losses = 0
        self.total_trades = 0
        self.last_boost_trade_count = 0

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.wins / self.total_trades

    def check_drawdown(self, current_equity: float, peak_equity: float) -> bool:
        if peak_equity <= 0:
            return True
        drawdown = (peak_equity - current_equity) / peak_equity
        return drawdown <= self.config.max_drawdown_limit

    def position_size(self, confidence_score: float, volatility: float, capital: float, price: float) -> float:
        effective_vol = max(volatility, self.config.min_volatility_floor)

        # Dynamic sizing: confidence weighted and volatility adjusted.
        raw_size = (
            self.config.base_position_size
            * max(abs(confidence_score), 0.12)
            * (1.0 / effective_vol)
            * self.risk_multiplier
        )

        capped_by_system = min(raw_size, self.config.max_position_size)
        capped_by_capital = (capital * self.config.max_capital_fraction) / max(price, 0.01)
        final_size = min(capped_by_system, capped_by_capital)
        return max(0.0, final_size)

    def stop_loss_pct(self, volatility: float) -> float:
        volatility_component = volatility * 1.4
        dynamic_stop = self.config.base_stop_loss + volatility_component
        return max(0.015, min(dynamic_stop, 0.14))

    def update_adaptive_risk(self, pnl: float) -> Optional[str]:
        self.total_trades += 1

        if pnl > 0:
            self.wins += 1
            self.loss_streak = 0
        else:
            self.losses += 1
            self.loss_streak += 1

        if self.loss_streak >= 3:
            previous = self.risk_multiplier
            self.risk_multiplier = max(
                self.config.min_risk_multiplier,
                self.risk_multiplier * self.config.loss_streak_cut_factor,
            )
            self.loss_streak = 0
            return (
                "3-loss streak detected: "
                f"risk multiplier reduced {previous:.2f} -> {self.risk_multiplier:.2f}"
            )

        if (
            self.total_trades >= self.config.min_trades_for_boost
            and (self.total_trades - self.last_boost_trade_count) >= self.config.boost_cooldown_trades
            and self.win_rate >= self.config.win_rate_boost_threshold
        ):
            previous = self.risk_multiplier
            self.risk_multiplier = min(
                self.config.max_risk_multiplier,
                self.risk_multiplier * self.config.win_rate_boost_factor,
            )
            self.last_boost_trade_count = self.total_trades
            if self.risk_multiplier > previous:
                return (
                    "Win rate strong: "
                    f"risk multiplier increased {previous:.2f} -> {self.risk_multiplier:.2f}"
                )

        return None

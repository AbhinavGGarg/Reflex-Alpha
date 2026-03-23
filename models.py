from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class WalletProfile:
    wallet_id: str
    wallet_type: str
    win_rate: float
    avg_trade_size: float


@dataclass
class WalletFlow:
    smart_buy: float = 0.0
    smart_sell: float = 0.0
    noise_buy: float = 0.0
    noise_sell: float = 0.0

    def total_volume(self) -> float:
        return self.smart_buy + self.smart_sell + self.noise_buy + self.noise_sell


@dataclass
class MarketDataPoint:
    timestamp: int
    price: float
    probability_shift: float
    volume: float
    orderbook_imbalance: float
    wallet_flow: WalletFlow
    spike_event: bool = False


@dataclass
class OpenPosition:
    side: str
    entry_price: float
    size: float
    entry_index: int
    confidence: float
    stop_loss_pct: float


@dataclass
class Trade:
    trade_id: int
    side: str
    entry_price: float
    exit_price: float
    size: float
    entry_index: int
    exit_index: int
    pnl: float
    confidence: float
    exit_reason: str


@dataclass
class BacktestResult:
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    adaptation_events: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)

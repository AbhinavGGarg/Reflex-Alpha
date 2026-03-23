from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from typing import List, Optional

from models import MarketDataPoint, WalletFlow, WalletProfile


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_float(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _extract_price(market_payload: dict) -> float:
    direct_fields = [
        market_payload.get("lastTradePrice"),
        market_payload.get("probability"),
        market_payload.get("last_trade_price"),
    ]
    for candidate in direct_fields:
        parsed = _safe_float(candidate, -1.0)
        if parsed > 0:
            return _clamp(parsed, 0.01, 0.99)

    outcome_prices = market_payload.get("outcomePrices")
    if isinstance(outcome_prices, str):
        try:
            decoded = json.loads(outcome_prices)
            if isinstance(decoded, list) and decoded:
                return _clamp(_safe_float(decoded[0], 0.5), 0.01, 0.99)
        except json.JSONDecodeError:
            pass
    if isinstance(outcome_prices, list) and outcome_prices:
        return _clamp(_safe_float(outcome_prices[0], 0.5), 0.01, 0.99)

    return 0.5


def _fetch_polymarket_snapshot(market_id: Optional[str] = None) -> Optional[dict]:
    """Try to fetch a live Polymarket snapshot.

    The engine falls back to simulation when this request fails or returns
    incomplete data.
    """
    if market_id:
        url = f"https://gamma-api.polymarket.com/markets/{market_id}"
    else:
        url = "https://gamma-api.polymarket.com/markets?limit=1"

    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None

    if isinstance(payload, list):
        if not payload:
            return None
        market = payload[0]
    elif isinstance(payload, dict):
        market = payload
    else:
        return None

    price = _extract_price(market)
    volume = _safe_float(market.get("volume"), 1200.0)
    return {"price": price, "volume": max(100.0, volume)}


def _build_wallet_profiles(rng: random.Random, smart_count: int = 10, noise_count: int = 24) -> List[WalletProfile]:
    profiles: List[WalletProfile] = []

    for index in range(smart_count):
        profiles.append(
            WalletProfile(
                wallet_id=f"smart_{index}",
                wallet_type="smart_money",
                win_rate=rng.uniform(0.60, 0.78),
                avg_trade_size=rng.uniform(40.0, 160.0),
            )
        )

    for index in range(noise_count):
        profiles.append(
            WalletProfile(
                wallet_id=f"noise_{index}",
                wallet_type="noise_trader",
                win_rate=rng.uniform(0.38, 0.55),
                avg_trade_size=rng.uniform(8.0, 90.0),
            )
        )

    return profiles


class MarketDataStream:
    """Stateful market stream that can produce realistic Polymarket-like ticks."""

    def __init__(
        self,
        seed: int = 7,
        market_id: Optional[str] = None,
        use_real_api: bool = False,
        start_price: float = 0.50,
    ) -> None:
        self.rng = random.Random(seed)
        self.market_id = market_id
        self.use_real_api = use_real_api
        self.current_price = _clamp(start_price, 0.02, 0.98)
        self.timestamp = int(time.time())
        self.regime_ticks_remaining = 0
        self.regime_drift = 0.0
        self.tick_count = 0
        self.wallets = _build_wallet_profiles(self.rng)
        self._roll_regime()

    def _roll_regime(self) -> None:
        # Regime drift creates trend phases (bullish, bearish, neutral).
        self.regime_drift = self.rng.uniform(-0.0085, 0.0085)
        self.regime_ticks_remaining = self.rng.randint(18, 72)

    def _simulate_wallet_flow(self, latent_move: float) -> WalletFlow:
        flow = WalletFlow()

        for wallet in self.wallets:
            trade_size = max(1.0, self.rng.gauss(wallet.avg_trade_size, wallet.avg_trade_size * 0.35))

            if wallet.wallet_type == "smart_money":
                expected_direction = 1 if latent_move >= 0 else -1
                aligned = self.rng.random() < wallet.win_rate
                direction = expected_direction if aligned else -expected_direction
                if direction > 0:
                    flow.smart_buy += trade_size
                else:
                    flow.smart_sell += trade_size
            else:
                # Noise traders are less consistent and often overreact.
                random_bias = self.rng.uniform(-1.0, 1.0)
                direction_value = latent_move * 0.25 + random_bias
                direction = 1 if direction_value >= 0 else -1
                if direction > 0:
                    flow.noise_buy += trade_size
                else:
                    flow.noise_sell += trade_size

        return flow

    def _simulate_tick(self) -> MarketDataPoint:
        if self.regime_ticks_remaining <= 0:
            self._roll_regime()
        self.regime_ticks_remaining -= 1

        micro_noise = self.rng.gauss(0.0, 0.009)
        spike = 0.0
        spike_event = False

        if self.rng.random() < 0.035:
            spike_event = True
            spike = self.rng.choice([-1.0, 1.0]) * self.rng.uniform(0.045, 0.12)

        latent_move = self.regime_drift + micro_noise + spike
        previous_price = self.current_price
        new_price = _clamp(previous_price * (1.0 + latent_move), 0.02, 0.98)

        probability_shift = new_price - previous_price
        volume = 1300.0 + abs(probability_shift) * 70000.0 + self.rng.gauss(0.0, 240.0)
        if spike_event:
            volume *= 1.9
        volume = max(200.0, volume)

        orderbook_imbalance = _clamp(probability_shift * 18.0 + self.rng.gauss(0.0, 0.28), -1.0, 1.0)
        wallet_flow = self._simulate_wallet_flow(latent_move)

        self.current_price = new_price
        self.timestamp += 60
        self.tick_count += 1

        return MarketDataPoint(
            timestamp=self.timestamp,
            price=new_price,
            probability_shift=probability_shift,
            volume=volume,
            orderbook_imbalance=orderbook_imbalance,
            wallet_flow=wallet_flow,
            spike_event=spike_event,
        )

    def fetch_next(self) -> MarketDataPoint:
        point = self._simulate_tick()

        # Blend periodic live API snapshots (when available) into the simulation.
        if self.use_real_api and self.tick_count % 10 == 0:
            snapshot = _fetch_polymarket_snapshot(self.market_id)
            if snapshot:
                prev_price = point.price - point.probability_shift
                blended_price = _clamp(point.price * 0.65 + snapshot["price"] * 0.35, 0.02, 0.98)
                point.probability_shift = blended_price - prev_price
                point.price = blended_price
                point.volume = max(point.volume, snapshot["volume"])
                self.current_price = blended_price

        return point

    def bootstrap(self, num_points: int) -> List[MarketDataPoint]:
        return [self.fetch_next() for _ in range(num_points)]


def get_market_data(
    num_points: int = 400,
    market_id: Optional[str] = None,
    use_real_api: bool = False,
    seed: int = 7,
) -> List[MarketDataPoint]:
    """Return market data for backtesting.

    If real API access is enabled but fails, the stream still returns a realistic
    synthetic market with trend regimes, noise, and event spikes.
    """
    stream = MarketDataStream(seed=seed, market_id=market_id, use_real_api=use_real_api)
    return stream.bootstrap(num_points)

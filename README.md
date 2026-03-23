# Reflex Alpha

Reflex Alpha is a backend-only adaptive trading engine built for **Orderflow 001**.
It models a Polymarket-style market, extracts multi-factor signals, executes simulated trades with slippage and delay, and reports measurable performance metrics.

## What Makes It Unique

- **Smart wallet behavior modeling**: wallets are simulated with win-rate and size profiles, separated into `smart_money` and `noise_trader` groups.
- **Multi-factor confidence engine**: momentum + wallet accumulation + orderbook pressure, penalized by volatility.
- **Adaptive risk system**:
  - If strategy loses 3 trades in a row, it automatically reduces aggressiveness.
  - If win rate is sustainably high, it increases aggressiveness.
- **Execution realism**: every fill includes slippage and delay.

## Project Structure

```text
/reflex-alpha
  /data
  /signals
  /strategy
  /execution
  /risk
  /backtest
  /metrics
  main.py
```

## Strategy Logic

### 1. Data Ingestion

`get_market_data()` returns Polymarket-like data with:
- price
- probability shift
- volume
- orderbook imbalance
- wallet flow

When API access is enabled, Reflex Alpha attempts to blend live snapshots from Polymarket and safely falls back to realistic simulation.

### 2. Signal Engine

Signals computed each tick:
- **Momentum signal**: rapid probability movement over a short lookback.
- **Volatility signal**: rolling standard deviation of returns.
- **Wallet signal**: smart wallet accumulation/distribution adjusted for noise wallet pressure.
- **Orderbook signal**: imbalance proxy for immediate buy/sell pressure.

### 3. Strategy Engine

Confidence score:

```python
confidence_score = (
    momentum_weight * momentum
    + wallet_weight * wallet_signal
    + orderbook_weight * orderbook_signal
    - volatility_weight * volatility
)
```

Decision rule:
- `BUY` if confidence > threshold
- `SELL` if confidence < -threshold
- otherwise `HOLD`

### 4. Execution Engine

Every trade uses:
- slippage (in basis points)
- delay (0..N ticks)

This avoids unrealistic instant fills.

### 5. Risk Engine

Dynamic size:

```python
position_size = base_size * abs(confidence) * (1 / volatility) * risk_multiplier
```

Then capped by:
- max position size
- max capital allocation

Risk controls:
- stop loss
- max drawdown guard
- adaptive risk multiplier based on streak and win rate

### 6. Backtest + Live Simulation

- **Backtest mode** runs across historical/simulated time-series and stores trades/equity curve.
- **Live simulation mode** streams incremental ticks and prints real-time decisions.

## Running Locally

From the `reflex-alpha` directory:

```bash
python3 main.py --mode backtest
```

Run both modes:

```bash
python3 main.py --mode both --points 500 --live-steps 50
```

Try blending live Polymarket snapshots:

```bash
python3 main.py --mode backtest --real-api
```

## Console Output Example

```text
[TRADE] BUY @ 0.62 | size: 120
[TRADE] SELL @ 0.68 | PnL: +9.60
[METRICS]
PnL: +124.30
Win Rate: 63.00%
Sharpe: 1.80
Max DD: -12.00%
Trades: 57
```

## Notes

- This is a simulation-first execution engine intended for hackathon velocity and measurable output.
- It is modular so each engine can be upgraded independently for real on-chain execution adapters.

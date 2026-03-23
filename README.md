# Reflex Alpha

Reflex Alpha is a **local Python trading simulation engine** for prediction markets.

It is not a web server and not an API.

## File Structure

- `main.py`
- `market.py`
- `signals.py`
- `strategy.py`
- `execution.py`
- `risk.py`

## Run

```bash
python main.py
```

Optional args:

```bash
python main.py --steps 200 --delay 0.1 --seed 7 --capital 10000
```

## What It Does

- Simulates market behavior with trend, noise, and event spikes
- Computes momentum, volatility, and smart-wallet signals
- Generates BUY/SELL/HOLD decisions
- Executes trades with slippage
- Applies dynamic risk sizing and adaptive aggressiveness
- Prints every time step with evolving PnL
- Prints final metrics:
  - Total PnL
  - Win Rate
  - Sharpe Ratio
  - Max Drawdown
  - Total Trades

# SOXL Lab

An educational systematic-trading and machine-learning project built around the
leveraged semiconductor ETFs **SOXL** (3x long) and **SOXS** (3x short).

The goal is to learn intraday mechanics, volatility decay, regime detection,
backtesting, and ML-in-finance from the ground up — not to run production
trading infrastructure. No real money is deployed until a strategy has passed
backtesting and forward paper-trading.

See [`CLAUDE.md`](./CLAUDE.md) for full project context, architecture roadmap,
and working conventions.

## Setup

```bash
pip install -r requirements.txt
```

## Structure

```
soxl-lab/
├── CLAUDE.md            # project context and conventions
├── requirements.txt
├── .gitignore            # ignores data/ and the venv
├── README.md
├── data/                 # cached pulls — gitignored, never commit raw data
├── notebooks/            # exploration
└── src/                  # reusable code (data.py, backtest.py, etc.)
```

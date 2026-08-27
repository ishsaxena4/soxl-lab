import os

import numpy as np
import pandas as pd
import yfinance as yf

from backtest import backtest, metrics
from strategy import vol_scaled_positions

# Same frozen-end discipline as data.py: yfinance's `end` is EXCLUSIVE, so
# "2026-07-15" includes every close through 2026-07-14. Kept as its own
# constant/cache rather than reusing data.py's -- this pull is deliberately
# separate (different ticker, different history length, different purpose:
# genuinely unseen out-of-sample data, not the SOXL series the strategy was
# designed on).
FROZEN_END = "2026-07-15"
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "qqq.csv")


def get_qqq_prices(start="1999-01-01", end=FROZEN_END, cache_path=CACHE_PATH, force_refresh=False):
    """
    Load QQQ daily closes from inception (~1999) to FROZEN_END, split/dividend
    adjusted (auto_adjust=True) -- same convention as data.py's get_prices().
    Cached to its own file (data/qqq.csv) so this stays reproducible day to
    day without touching the pinned SOXL/SOXS/SOXX cache.
    """
    if os.path.exists(cache_path) and not force_refresh:
        return pd.read_csv(cache_path, index_col=0, parse_dates=True)["QQQ"]

    data = yf.download(["QQQ"], start=start, end=end, auto_adjust=True)["Close"].dropna()

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    data.to_csv(cache_path)

    return data["QQQ"]


qqq = get_qqq_prices()
qqq_ret = qqq.pct_change().dropna()

# Simulate a daily-reset 3x-QQQ fund. Must compound MULTIPLICATIVELY
# (equity_t = equity_{t-1} * (1 + 3*r_t)), not additively (e.g. cumsum of
# 3*r_t). A daily-reset leveraged fund's return is bounded below at -100%
# for any single day -- it can decay toward zero but never go negative.
# Additive accumulation has no such floor and would let the synthetic
# "price" go negative, which is not physically possible for a fund's NAV.
synthetic_prices = (1 + 3 * qqq_ret).cumprod()

# Set k relative to this instrument's own vol level rather than reusing
# vol_scaled_positions' SOXL-tuned default (k=0.60), since a 3x-QQQ fund has
# a different typical vol regime than SOXL.
# NOTE: using the FULL-SAMPLE average vol to set k technically peeks at the
# whole history when choosing a strategy parameter. This is acceptable here
# because it's a coarse anchor -- roughly re-centering k to this fund's
# typical vol level -- not a tuned/optimized parameter; we are not fitting k
# to maximize any performance metric, just scaling it sensibly.
synthetic_ret = synthetic_prices.pct_change()
realized_vol = synthetic_ret.rolling(20).std() * np.sqrt(252)
avg_vol = realized_vol.mean()
k = 0.61 * avg_vol

print(f"Measured full-sample avg 20-day annualized vol (synthetic 3x-QQQ): {avg_vol:.2%}")
print(f"k = 0.61 * avg_vol = {k:.4f}")

# Positions computed on the FULL history, then sliced per window below --
# same continuity reasoning as split_test.py: slicing prices first would
# restart each window's 20-day rolling vol cold, with no real prior data to
# look back on right at the window boundary.
bh_positions = pd.Series(1.0, index=synthetic_prices.index)
vs_positions = vol_scaled_positions(synthetic_prices, lookback=20, k=k).fillna(0.0)

strategies = {
    "Buy & hold": bh_positions,
    "Vol scaled": vs_positions,
}


def print_block(label, prices_slice, strategies_slice):
    start = prices_slice.index.min().date()
    end = prices_slice.index.max().date()
    print(f"\n{label}  ({start} to {end}, {len(prices_slice)} days)")
    for name, positions_slice in strategies_slice.items():
        results = backtest(prices_slice, positions_slice)
        m = metrics(results)
        total_turnover = results["turnover"].sum()
        print(f"  {name:12s}  CAGR {m['CAGR']:7.2%}  Vol {m['Volatility']:6.2%}  "
              f"Sharpe {m['Sharpe']:.3f}  MaxDD {m['Max drawdown']:7.2%}  "
              f"Turnover {total_turnover:6.2f}")


print_block("Full sample (1999-2026)", synthetic_prices, strategies)

CRISIS_WINDOWS = {
    "Dot-com (2000-2002)":        ("2000-01-01", "2002-12-31"),
    "GFC (2007-2009)":            ("2007-01-01", "2009-12-31"),
    "COVID (2020-02 to 2020-06)": ("2020-02-01", "2020-06-30"),
    "2022":                       ("2022-01-01", "2022-12-31"),
}

for label, (start, end) in CRISIS_WINDOWS.items():
    mask = (synthetic_prices.index >= start) & (synthetic_prices.index <= end)
    prices_slice = synthetic_prices[mask]
    strategies_slice = {name: pos[mask] for name, pos in strategies.items()}
    print_block(label, prices_slice, strategies_slice)

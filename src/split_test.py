import pandas as pd

from data import get_prices
from backtest import backtest, metrics
from strategy import vol_scaled_positions

prices = get_prices()["SOXL"]

# Build positions on the FULL history first, then slice below -- deliberate.
# vol_scaled_positions() uses a 20-day rolling window, so if we sliced prices
# to the test half BEFORE computing positions, the first ~20 days of the test
# half would see a rolling window restarting cold (no prior data to look
# back on), giving artificially wrong/NaN vol estimates right at the split.
# Computing on the full series first means the test half's early days still
# roll back into real 2021 data, exactly as they would in live trading.
bh_positions_full = pd.Series(1.0, index=prices.index)
vs_positions_full = vol_scaled_positions(prices).fillna(0.0)

SPLIT_DATE = "2022-01-01"
halves = {
    "Train (2015-2021)": prices.index < SPLIT_DATE,
    "Test (2022-2026)":  prices.index >= SPLIT_DATE,
}

strategies_full = {
    "Buy & hold": bh_positions_full,
    "Vol scaled": vs_positions_full,
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


for label, mask in halves.items():
    prices_slice = prices[mask]
    strategies_slice = {name: pos[mask] for name, pos in strategies_full.items()}
    print_block(label, prices_slice, strategies_slice)

# Full-sample reference row, so train/test can be compared against the whole.
print_block("Full sample (2015-2026)", prices, strategies_full)

import os

import yfinance as yf
import pandas as pd

# Pinned so metrics stay stable across a multi-day work session instead of
# shifting every time a new live trading day appends to the feed.
# yfinance's `end` is EXCLUSIVE, so "2026-07-15" includes every close
# through 2026-07-14. To roll the window forward later, change this date,
# delete data/prices.csv (or call get_prices(force_refresh=True)), and rerun.
FROZEN_END = "2026-07-15"

# Cache file lives next to this file's parent (repo root's data/), resolved
# from __file__ so it doesn't matter what directory a script is run from.
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "prices.csv")


def get_prices(tickers=("SOXL", "SOXS", "SOXX"), start="2015-01-01", end=FROZEN_END,
               cache_path=CACHE_PATH, force_refresh=False):
    """
    Load daily closing prices, split/dividend-adjusted (auto_adjust=True).
    Returns a DataFrame indexed by date, one column per ticker.

    If `cache_path` already exists, reads from it instead of hitting the
    network -- this is what makes results reproducible day to day. Pass
    force_refresh=True to re-download and overwrite the cache (e.g. after
    deliberately moving FROZEN_END forward). The cache is assumed to match
    the tickers/start/end it was built with; it isn't re-validated per call.
    """
    if os.path.exists(cache_path) and not force_refresh:
        return pd.read_csv(cache_path, index_col=0, parse_dates=True)

    data = yf.download(list(tickers), start=start, end=end, auto_adjust=True)["Close"].dropna()

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    data.to_csv(cache_path)

    return data


if __name__ == "__main__":
    data = get_prices()

    # Daily simple returns: (price_today / price_yesterday) - 1
    rets = data.pct_change().dropna()

    # --- The real measurement: actual leveraged return vs the naive "Nx" assumption ---
    # A naive investor assumes SOXL delivers 3x the index's return OVER ANY PERIOD.
    # Let's test that year by year.
    def period_return(df):
        return (1 + df).prod() - 1          # compound the daily returns

    yearly = rets.groupby(rets.index.year).apply(period_return)
    yearly["3x_SOXX"]  = 3 * yearly["SOXX"]          # what naive 3x would give
    yearly["gap_SOXL"] = yearly["SOXL"] - yearly["3x_SOXX"]  # actual minus naive

    print(yearly[["SOXX", "SOXL", "3x_SOXX", "gap_SOXL"]].round(3))

import numpy as np
import pandas as pd

from backtest import backtest, metrics
from data import get_prices


def vol_filter_positions(prices, lookback=20, vol_threshold=0.60):
    """
    Regime filter: long SOXL when trailing realized vol is BELOW threshold,
    flat when above. No directional view -- this is purely a risk filter.

    vol_threshold is annualized (0.60 = 60% annualized vol).
    """
    rets = prices.pct_change()
    realized_vol = rets.rolling(lookback).std() * np.sqrt(252)

    # 1.0 = long, 0.0 = flat. Computed from data up to and including today's
    # close; the engine's shift(1) ensures it only earns tomorrow's return.
    positions = (realized_vol < vol_threshold).astype(float)
    return positions


def momentum_filter_positions(prices, lookback=20):
    """
    Regime filter: long SOXL when trailing N-day cumulative return is
    positive (an uptrend), flat when negative. Pure trend filter -- no
    volatility information.

    Deliberately built from the same shape as vol_filter_positions --
    rolling(lookback) over daily returns -- just .sum() instead of .std(),
    so the two filters are directly comparable on the same window.
    """
    rets = prices.pct_change()
    momentum = rets.rolling(lookback).sum()

    # 1.0 = long, 0.0 = flat. Computed from data up to and including today's
    # close; the engine's shift(1) ensures it only earns tomorrow's return.
    positions = (momentum > 0).astype(float)
    return positions


def combined_filter_positions(prices, lookback=20, vol_threshold=0.60):
    """Long only when trend is up AND vol is not spiking; flat otherwise."""
    mom = momentum_filter_positions(prices, lookback)
    vol = vol_filter_positions(prices, lookback, vol_threshold)
    return (mom * vol)   # 1.0 only if BOTH are 1.0


def vol_scaled_positions(prices, lookback=20, k=0.60):
    """
    Graduated (continuous) sizing: position = k / realized_vol, clipped to [0, 1].
    Fully long when vol <= k, scaling smoothly toward flat as vol rises above k.
    No binary on/off, no directional view -- pure vol-scaled exposure.
    """
    rets = prices.pct_change()
    realized_vol = rets.rolling(lookback).std() * np.sqrt(252)
    raw = k / realized_vol
    positions = raw.clip(0.0, 1.0)
    return positions


if __name__ == "__main__":
    # Compare buy-and-hold against all four regime strategies on the same
    # asset and window, so their Sharpe/drawdown tradeoffs sit side by side.
    prices = get_prices()["SOXL"]
    cost_bps = 5.0

    runs = {
        "Buy & hold": pd.Series(1.0, index=prices.index),
        "Vol filter": vol_filter_positions(prices).fillna(0.0),
        "Momentum":   momentum_filter_positions(prices).fillna(0.0),
        "Combined":   combined_filter_positions(prices).fillna(0.0),
        "Vol scaled": vol_scaled_positions(prices).fillna(0.0),
    }

    for name, positions in runs.items():
        results = backtest(prices, positions, cost_bps=cost_bps)
        m = metrics(results)
        # "Trades" counts any day with nonzero turnover, so it understates
        # churn for continuous-position strategies (e.g. vol scaled), where
        # most days are small resizes rather than full entries/exits. Total
        # turnover (sum of daily |position change|) and the cost it actually
        # cost is the honest measure and applies the same way to every
        # strategy, binary or continuous.
        total_turnover = results["turnover"].sum()
        total_cost_drag = total_turnover * (cost_bps / 10_000.0)
        print(f"{name:12s}  CAGR {m['CAGR']:7.2%}  Vol {m['Volatility']:6.2%}  "
              f"Sharpe {m['Sharpe']:.3f}  MaxDD {m['Max drawdown']:7.2%}  "
              f"Trades {m['Trades']}  Turnover {total_turnover:6.2f}  "
              f"Cost drag {total_cost_drag:.2%}")

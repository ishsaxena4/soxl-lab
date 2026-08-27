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


def regime_switch_positions(prices, lookback=20, k=0.60, trend_window=20,
                            vol_percentile=0.60, vol_lookback=252,
                            up_mult=1.5, down_floor=0.0):
    """
    Three-bucket regime-switch sizing. Every day falls into exactly ONE of
    three regimes, decided by a RELATIVE vol level and a trend SIGN:

      1. low vol  (v <  threshold)              -> clip(k / v, 0, 1)
      2. high vol (v >= threshold), trend  > 0  -> clip(up_mult * k / v, 0, 1)
      3. high vol (v >= threshold), trend <= 0  -> down_floor

    Bucket 1 is byte-for-byte what vol_scaled_positions does. Bucket 2 is the
    only one that can size ABOVE plain vol-scaling. So the ONLY difference
    between this strategy and vol_scaled_positions is the bucketing -- any
    performance difference is attributable to that and nothing else.

    lookback / k mirror vol_scaled_positions exactly. trend_window is the
    rolling-sum window for the trend sign; vol_percentile / vol_lookback set
    the trailing "high vol" threshold; up_mult scales bucket 2; down_floor is
    the flat target in bucket 3.
    """
    rets = prices.pct_change()

    # --- Signal 1: realized vol ------------------------------------------
    # Identical to vol_scaled_positions: same rolling-std window, same
    # sqrt(252) annualization. Not a new vol measure.
    realized_vol = rets.rolling(lookback).std() * np.sqrt(252)

    # "High vol" is relative to this asset's OWN recent vol history, not an
    # absolute number. Threshold at day t = the vol_percentile-th quantile of
    # the last vol_lookback realized-vol observations.
    #
    # LEAK-FREE: pandas' rolling window at row t covers rows
    # [t - vol_lookback + 1 .. t] -- trailing, closed on the right. It uses
    # today's vol and older values, never tomorrow's. (A full-sample
    # realized_vol.quantile(...) WOULD leak the future; that is exactly what
    # this line avoids.)
    vol_threshold = realized_vol.rolling(vol_lookback).quantile(vol_percentile)

    # --- Signal 2: trend direction ---------------------------------------
    # Rolling SUM of daily returns, same shape momentum_filter_positions uses.
    # Only its SIGN matters here. Not an MA crossover, not price momentum.
    trend_sum = rets.rolling(trend_window).sum()

    # --- Bucket assignment ------------------------------------------------
    is_high_vol = realized_vol >= vol_threshold
    high_up = is_high_vol & (trend_sum > 0)     # strictly positive
    high_down = is_high_vol & (trend_sum <= 0)  # zero counts as "down"

    # Warm-up: until lookback, trend_window AND vol_lookback are all filled,
    # any comparison against NaN is False, so is_high_vol is False and those
    # days fall to bucket 1 -- where the size is itself NaN, which the
    # caller's .fillna(0.0) turns into "flat". Same convention every other
    # strategy in this file uses. In practice the first ~252 days behave as
    # plain vol-scaling, which is honest: you cannot know what "high vol for
    # this asset" means before you have a vol history to compare against.

    low_vol_size = (k / realized_vol).clip(0.0, 1.0)            # bucket 1
    high_up_size = (up_mult * k / realized_vol).clip(0.0, 1.0)  # bucket 2

    # Start from bucket 1 everywhere, then overwrite the two high-vol buckets.
    positions = low_vol_size.copy()
    positions[high_up] = high_up_size[high_up]
    positions[high_down] = down_floor

    # TIMING: no .shift() here -- same basis as every other strategy in this
    # file. Each value is computed from data up to and INCLUDING that day's
    # close; backtest() applies its own shift(1) so the position only earns
    # the NEXT day's return.
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

import numpy as np
import pandas as pd

from data import get_prices

TRADING_DAYS = 252


def backtest(prices, positions, cost_bps=5.0):
    """
    prices:    daily price Series for ONE instrument (e.g. SOXL close).
    positions: desired exposure per day, same index as prices.
               1.0 = fully long, 0.0 = flat. Chosen using info up to that day.
    cost_bps:  one-way trading cost in basis points (1 bp = 0.01%).
               5 bps is a reasonable retail estimate for a liquid ETF
               (spread + slippage). Commission assumed zero.
    """
    asset_ret = prices.pct_change()

    # A position chosen at day t's close only earns day t+1's return,
    # so shift positions forward one day before multiplying.
    # This single line is what prevents look-ahead bias.
    # fillna(0.0): before the backtest window starts there's no known prior
    # position, so treat it as flat. Without this, pos.diff() on the very
    # first real day computes (1.0 - NaN) = NaN, which poisons that day's
    # strat_ret and gets silently dropped -- losing both the first day's
    # return AND the cost of entering the very first position.
    pos = positions.shift(1).fillna(0.0)      # position actually HELD during day t

    # Turnover: how much the held position changed today. Going 0 -> 1 costs
    # one unit; holding steady costs nothing. This is what makes churn expensive.
    turnover = pos.diff().abs()
    cost = turnover * (cost_bps / 10_000.0)

    strat_ret = pos * asset_ret - cost
    equity = (1 + strat_ret).cumprod()         # what $1 grows to

    return pd.DataFrame({
        "asset_ret": asset_ret,
        "position":  pos,
        "turnover":  turnover,
        "strat_ret": strat_ret,
        "equity":    equity,
    }).dropna()


def metrics(results):
    r = results["strat_ret"]
    equity = results["equity"]
    n = len(r)

    cagr = equity.iloc[-1] ** (TRADING_DAYS / n) - 1
    vol = r.std() * np.sqrt(TRADING_DAYS)          # annualize daily vol
    sharpe = (r.mean() / r.std()) * np.sqrt(TRADING_DAYS) if r.std() > 0 else np.nan

    # Drawdown: how far below the running peak are we, every day?
    drawdown = equity / equity.cummax() - 1
    max_dd = drawdown.min()

    return {
        "CAGR":         cagr,
        "Volatility":   vol,
        "Sharpe":       sharpe,
        "Max drawdown": max_dd,
        "Trades":       int((results["turnover"] > 0).sum()),
    }


if __name__ == "__main__":
    # Trivial validation strategy per Module 2: buy-and-hold on SOXL.
    # Positions is fully long (1.0) every single day.
    prices = get_prices()["SOXL"]
    positions = pd.Series(1.0, index=prices.index)

    results = backtest(prices, positions)

    # Validate the engine on the one case with a hand-computable answer:
    # a static buy-and-hold enters once (day 1) and never trades again, so
    # equity = (gross day-1 return, net of its one-time entry cost)
    #          * (the plain, uncosted compounding of every day after that).
    cost = 5.0 / 10_000.0
    day1_ret = prices.iloc[1] / prices.iloc[0] - 1
    expected = (1 + day1_ret - cost) * (prices.iloc[-1] / prices.iloc[1])
    actual = results["equity"].iloc[-1]
    assert abs(actual - expected) < 1e-9, f"Engine mismatch: {actual} vs {expected}"
    print(f"Validation passed: engine reproduces buy-and-hold net of entry cost ({actual:.6f})")

    total_return = results["equity"].iloc[-1] - 1
    n_days = len(results)

    print(results.tail())
    print(f"\nDays in backtest: {n_days}")
    print(f"Final equity (per $1 invested): {results['equity'].iloc[-1]:.3f}")
    print(f"Total return: {total_return:.2%}")

    print("\nMetrics:")
    for name, value in metrics(results).items():
        if name == "Trades":
            print(f"  {name}: {value}")
        elif name in ("CAGR", "Volatility", "Max drawdown"):
            print(f"  {name}: {value:.2%}")
        else:
            print(f"  {name}: {value:.3f}")

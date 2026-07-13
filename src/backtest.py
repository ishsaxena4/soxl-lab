import pandas as pd

from data import get_prices


def backtest(prices, positions):
    """
    prices:    daily price Series for ONE instrument (e.g. SOXL close).
    positions: desired exposure per day, same index as prices.
               1.0 = fully long, 0.0 = flat. Chosen using info up to that day.
    """
    asset_ret = prices.pct_change()          # return from yesterday to today

    # A position chosen at day t's close only earns day t+1's return,
    # so shift positions forward one day before multiplying.
    # This single line is what prevents look-ahead bias.
    strat_ret = positions.shift(1) * asset_ret

    equity = (1 + strat_ret).cumprod()       # what $1 grows to
    return pd.DataFrame({
        "asset_ret": asset_ret,
        "position":  positions.shift(1),
        "strat_ret": strat_ret,
        "equity":    equity,
    }).dropna()


if __name__ == "__main__":
    # Trivial validation strategy per Module 2: buy-and-hold on SOXL.
    # Positions is fully long (1.0) every single day.
    prices = get_prices()["SOXL"]
    positions = pd.Series(1.0, index=prices.index)
    midpoint = len(positions) // 2
    positions.iloc[midpoint:] = 0.0 

    flip_date = prices.index[midpoint]
    print(f"Backtest: buy-and-hold SOXL until {flip_date.date()}")

    results = backtest(prices, positions)

    # expected = prices.iloc[-1] / prices.iloc[0]
    #actual = results["equity"].iloc[-1]
    # assert abs(actual - expected) < 1e-9, f"Engine mismatch: {actual} vs {expected}"
    # print(f"Validation passed: engine reproduces buy-and-hold to <1e-9 ({actual:.6f})")

    total_return = results["equity"].iloc[-1] - 1
    n_days = len(results)

    print(results.tail())
    print(results.iloc[midpoint-3 : midpoint+3])
    print(f"\nDays in backtest: {n_days}")
    print(f"Final equity (per $1 invested): {results['equity'].iloc[-1]:.3f}")
    print(f"Total return: {total_return:.2%}")

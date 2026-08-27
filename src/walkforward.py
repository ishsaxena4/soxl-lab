"""
Module 3, Phase 1 -- anchored (expanding) walk-forward out-of-sample harness.

Purpose: stop judging vol-scaling on a single train/test split (Module 2's
split_test.py was a one-shot proof of concept). Here we cut the history into
several NON-OVERLAPPING out-of-sample test blocks and ask a consistency
question: in how many separate, unseen blocks does vol-scaling actually beat
buy-and-hold on Sharpe? One win is luck; four is a pattern; two is noise.

Everything here reuses existing repo code -- get_prices(), backtest(),
metrics(), vol_scaled_positions() -- so the numbers are directly comparable
to every other result in the repo.

IMPORTABLE: the config constants and the fold machinery (build_folds,
evaluate_block, fmt_span) live at module level, so another script can reuse
this exact fold scheme. The run itself is under the __main__ guard at the
bottom, so importing this module does NOT execute a backtest or print.
"""

import pandas as pd

from data import get_prices
from backtest import backtest, metrics
from strategy import vol_scaled_positions

# --- Configuration -------------------------------------------------------
# Same asset, same cost model, and same vol-scaling parameters that
# strategy.py's __main__ uses, so results line up with the incumbent numbers.
TICKER = "SOXL"
COST_BPS = 5.0
LOOKBACK = 20      # strategy.py's vol_scaled_positions default
K = 0.60           # strategy.py's vol_scaled_positions default

MIN_TRAIN_YEARS = 5      # first train window: 2015-01 through end-2019
TEST_MONTHS = 18         # 1.5-year test blocks
STEP_MONTHS = TEST_MONTHS  # step == test length => test blocks never overlap


# --- Fold construction ---------------------------------------------------
def build_folds(index, min_train_years, test_months, step_months):
    """
    Build anchored (expanding-window) walk-forward folds.

    "Anchored" means every train window starts at the SAME first date -- the
    beginning of history -- and only its END moves forward. Fold 1 trains on
    2015-2019, fold 2 on 2015 through mid-2021, and so on. The train window
    grows; it never slides off the early data. That's deliberate: we want the
    2018 crash inside every single training window, not just the first.

    Each fold's test block starts exactly where its train window ends, and the
    next fold's test block starts where this one ended. Because we step by the
    test length, the test blocks tile the timeline without overlapping -- no
    day of out-of-sample data is ever counted twice.

    Returns a list of (train_start, train_end, test_start, test_end)
    Timestamps. Boundaries are half-open [start, end): train_end == test_start
    is the same instant, and belongs to the test block.
    """
    history_start = index.min()
    history_end = index.max()

    # End of the FIRST train window. Every later train window ends at that
    # fold's test_start instead (see the loop below).
    first_train_end = history_start + pd.DateOffset(years=min_train_years)

    folds = []
    test_start = first_train_end
    while True:
        test_end = test_start + pd.DateOffset(months=test_months)

        # Only accept COMPLETE test blocks. A final stub block of a few months
        # would have far fewer days than the others, so its Sharpe would be
        # much noisier -- and it would get an equal vote in the win/loss
        # tally. Better to drop it than to let it distort the count.
        if test_end > history_end:
            break

        # Anchored: train always starts at history_start; its end walks
        # forward to meet this fold's test block.
        folds.append((history_start, test_start, test_start, test_end))

        test_start = test_start + pd.DateOffset(months=step_months)

    return folds


# --- Per-fold evaluation -------------------------------------------------
def evaluate_block(prices_full, positions_full, start, end, cost_bps):
    """
    Backtest one strategy over the half-open date window [start, end).

    ***** This is where the continuity-guard slicing happens. *****
    Both the prices and the ALREADY-COMPUTED full-history positions are cut
    with the same mask. We are selecting from a finished series, not
    recomputing one -- no rolling window is restarted here.
    """
    mask = (prices_full.index >= start) & (prices_full.index < end)

    prices_slice = prices_full[mask]
    positions_slice = positions_full[mask]      # <-- slice, never recompute

    results = backtest(prices_slice, positions_slice, cost_bps=cost_bps)
    return results, metrics(results)


def fmt_span(prices_full, start, end):
    """Human-readable actual traded span -- calendar bounds snapped to real
    trading days, plus the day count, so a short fold is obvious on sight."""
    mask = (prices_full.index >= start) & (prices_full.index < end)
    idx = prices_full.index[mask]
    return f"{idx.min().date()} -> {idx.max().date()} ({len(idx)} days)"


if __name__ == "__main__":
    # --- Data and full-history position series ---------------------------
    prices = get_prices()[TICKER]

    # ***** CONTINUITY GUARD *****
    # Positions are computed ONCE, here, on the FULL price history -- before any
    # fold exists. This is the single most important line in the file:
    vs_positions_full = vol_scaled_positions(prices, lookback=LOOKBACK, k=K).fillna(0.0)
    #
    # Why it must happen here and not inside the fold loop: vol_scaled_positions()
    # uses a 20-day rolling std. If we sliced prices down to a test block and THEN
    # computed vol, the rolling window would restart cold at the block's first day
    # -- the first ~20 days would be NaN or computed from an underfilled window,
    # i.e. garbage, and .fillna(0.0) would silently turn that garbage into "flat".
    # Every fold would open with ~20 fake days of sitting on the sidelines.
    #
    # Computing on the full series means a test block's opening days still roll
    # back into the real prices immediately preceding them -- exactly the
    # information a live trader would have had on that morning.
    #
    # This is NOT look-ahead: the rolling window only ever looks BACKWARD, and
    # backtest() shifts positions forward one day before applying returns. A
    # position on a test-block day is a function of prices at or before that day
    # only. Slicing after the fact removes days; it never lets a later day inform
    # an earlier one.

    bh_positions_full = pd.Series(1.0, index=prices.index)

    strategies_full = {
        "Vol scaled": vs_positions_full,
        "Buy & hold": bh_positions_full,
    }

    folds = build_folds(prices.index, MIN_TRAIN_YEARS, TEST_MONTHS, STEP_MONTHS)

    print(f"Anchored walk-forward on {TICKER}: "
          f"{MIN_TRAIN_YEARS}y minimum anchored train window, "
          f"{TEST_MONTHS}-month non-overlapping test blocks, "
          f"{COST_BPS:.0f} bps one-way costs, vol-scaling k={K} / {LOOKBACK}d.")
    print(f"Full history available: {prices.index.min().date()} -> "
          f"{prices.index.max().date()} ({len(prices)} days), {len(folds)} folds.\n")

    sharpe_wins = 0
    sharpe_losses = 0

    for fold_number, (train_start, train_end, test_start, test_end) in enumerate(folds, start=1):
        print(f"--- Fold {fold_number} ---")
        print(f"  Train (in-sample):     {fmt_span(prices, train_start, train_end)}")
        print(f"  Test  (OUT-of-sample): {fmt_span(prices, test_start, test_end)}")

        fold_sharpes = {}
        for name, positions_full in strategies_full.items():
            results, m = evaluate_block(prices, positions_full, test_start, test_end, COST_BPS)
            fold_sharpes[name] = m["Sharpe"]

            # Turnover, not trade count, is the honest churn measure for a
            # continuous-sizing strategy -- see CLAUDE.md.
            total_turnover = results["turnover"].sum()
            print(f"    {name:12s}  CAGR {m['CAGR']:8.2%}  Vol {m['Volatility']:6.2%}  "
                  f"Sharpe {m['Sharpe']:7.3f}  MaxDD {m['Max drawdown']:8.2%}  "
                  f"Turnover {total_turnover:6.2f}")

        # The consistency read: did vol-scaling beat buy-and-hold on THIS unseen
        # block? Ties count as losses -- the burden of proof is on the strategy.
        if fold_sharpes["Vol scaled"] > fold_sharpes["Buy & hold"]:
            sharpe_wins += 1
            verdict = "WIN  (vol-scaled Sharpe higher)"
        else:
            sharpe_losses += 1
            verdict = "LOSS (buy-and-hold Sharpe >= vol-scaled)"
        edge = fold_sharpes["Vol scaled"] - fold_sharpes["Buy & hold"]
        print(f"    -> {verdict}, Sharpe edge {edge:+.3f}\n")

    # --- Aggregate: the whole point of the exercise ----------------------
    print("=== Walk-forward summary ===")
    print(f"  Out-of-sample folds evaluated: {len(folds)}")
    print(f"  Vol-scaled beats buy-and-hold on Sharpe: {sharpe_wins} / {len(folds)} folds")
    print(f"  Buy-and-hold wins or ties:               {sharpe_losses} / {len(folds)} folds")
    print("\n  Read this as a CONSISTENCY check, not a performance number. A")
    print("  strategy that wins 4/4 unseen blocks is behaving like a real effect;")
    print("  2/4 is a coin flip dressed up as an edge. The per-fold CAGR/MaxDD")
    print("  above tell you WHERE the wins and losses came from.")

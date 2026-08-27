"""
Module 3, Phase 2 -- run the three-bucket regime switch through the Phase 1
walk-forward harness.

Four strategies, side by side on every fold:
  vol_scaled  -- the incumbent sizing layer (Phase 1's winner-by-mechanism)
  regime_1p0  -- regime switch, NO up-aggression      (up_mult=1.0)
  regime_1p5  -- regime switch, conservative aggression (up_mult=1.5)
  regime_2p0  -- regime switch, more aggression      (up_mult=2.0)

regime_1p0 is the control. At up_mult=1.0 the bucket-2 size is
clip(1.0 * k / v, 0, 1) -- algebraically the SAME expression as bucket 1 and
as plain vol_scaled. So regime_1p0 differs from vol_scaled in exactly ONE
place: the high_vol_down bucket, where it goes to down_floor instead of
staying vol-scaled. That splits the architecture into its two halves and lets
each be attributed separately:

  regime_1p0 vs vol_scaled  ->  the DOWN-CUT alone (defensive half)
  regime_1p5 vs regime_1p0  ->  the UP-LEVER alone (offensive half)

These support several independent comparisons, deliberately kept apart in the
output below rather than merged into one win/loss -- merging would confound
"is the idea sound" with "is the knob set right" with "which half did the
work":
  (A) ARCHITECTURE  -- regime_1p5 vs vol_scaled: does directional bucketing
      help at all, at the conservative setting?
  (B) AGGRESSION    -- regime_2p0 vs regime_1p5: does turning the up_mult
      knob up help, holding the architecture fixed?
  (C) DOWN-CUT ONLY -- regime_1p0 vs vol_scaled: does cutting to flat in
      high-vol-down help, with the up-lever neutralised?
  (D) UP-LEVER 1.5  -- regime_1p5 vs regime_1p0: what does the up-lever add
      on top of the down-cut?
  (E) UP-LEVER 2.0  -- regime_2p0 vs regime_1p0: same, at full aggression.

Fold scheme, cost model, and slicing are imported from walkforward.py -- not
reimplemented -- so these numbers sit on exactly the Phase 1 harness.
"""

import numpy as np
import pandas as pd

from data import get_prices
from strategy import vol_scaled_positions, regime_switch_positions

# walkforward.py keeps its run under an `if __name__ == "__main__":` guard, so
# this import pulls in the fold machinery and config WITHOUT executing a
# backtest or printing anything.
from walkforward import (
    build_folds, evaluate_block, fmt_span,
    TICKER, COST_BPS, LOOKBACK, K,
    MIN_TRAIN_YEARS, TEST_MONTHS, STEP_MONTHS,
)

# Regime-switch settings. Only up_mult differs between the three variants;
# every other argument stays at the function's defaults, so the bucketing is
# identical across them and only the size inside bucket 2 changes.
UP_MULT_NEUTRAL = 1.0        # control: bucket 2 sized exactly like vol_scaled
UP_MULT_CONSERVATIVE = 1.5
UP_MULT_AGGRESSIVE = 2.0
DOWN_FLOOR = 0.0

# Bucket-classification defaults, mirrored from regime_switch_positions'
# signature so the occupancy diagnostic below matches what the strategy did.
TREND_WINDOW = 20
VOL_PERCENTILE = 0.60
VOL_LOOKBACK = 252

BUCKET_LABELS = ("low_vol", "high_vol_up", "high_vol_down")


# --- Data and full-history position series -------------------------------
prices = get_prices()[TICKER]

# ***** CONTINUITY GUARD *****
# Every position series is computed ONCE, here, on the FULL price history --
# before any fold exists. Same pattern as walkforward.py's __main__ block, for
# the same reason: regime_switch_positions uses a 20-day rolling std AND a
# 252-day rolling quantile. Slicing prices to a test block and recomputing
# inside the fold would restart both windows cold, making the block's first
# ~272 days NaN/underfilled -- which .fillna(0.0) would silently convert into
# a fake "flat" opening. Computing on the full series means each block's
# opening days roll back into the real prices preceding them, exactly as a
# live trader's would.
#
# Not look-ahead: every window here looks strictly BACKWARD, and backtest()
# applies its own shift(1) before returns. Slicing a finished backward-looking
# series removes days; it never lets a later day inform an earlier one.
vs_positions_full = vol_scaled_positions(
    prices, lookback=LOOKBACK, k=K).fillna(0.0)

r10_positions_full = regime_switch_positions(
    prices, lookback=LOOKBACK, k=K,
    up_mult=UP_MULT_NEUTRAL, down_floor=DOWN_FLOOR).fillna(0.0)

r15_positions_full = regime_switch_positions(
    prices, lookback=LOOKBACK, k=K,
    up_mult=UP_MULT_CONSERVATIVE, down_floor=DOWN_FLOOR).fillna(0.0)

r20_positions_full = regime_switch_positions(
    prices, lookback=LOOKBACK, k=K,
    up_mult=UP_MULT_AGGRESSIVE, down_floor=DOWN_FLOOR).fillna(0.0)

# Dict order fixes the row order in every per-fold table below.
strategies_full = {
    "vol_scaled": vs_positions_full,
    "regime_1p0": r10_positions_full,
    "regime_1p5": r15_positions_full,
    "regime_2p0": r20_positions_full,
}


# --- Regime occupancy diagnostic -----------------------------------------
# NOTE ON DUPLICATION: regime_switch_positions returns only a position
# series, and strategy.py is not to be modified, so the bucket labels have to
# be re-derived here. The four expressions below are copied VERBATIM from
# regime_switch_positions -- same windows, same comparisons, same treatment of
# NaN warm-up days (any comparison against NaN is False, so warm-up falls to
# low_vol). If the strategy's bucketing is ever edited, this block must be
# edited in lockstep or the diagnostic will silently describe the wrong thing.
#
# Also computed ONCE on full history, for the same continuity reason as above.
_rets = prices.pct_change()
_realized_vol = _rets.rolling(LOOKBACK).std() * np.sqrt(252)
_vol_threshold = _realized_vol.rolling(VOL_LOOKBACK).quantile(VOL_PERCENTILE)
_trend_sum = _rets.rolling(TREND_WINDOW).sum()

_is_high_vol = _realized_vol >= _vol_threshold
_high_up = _is_high_vol & (_trend_sum > 0)
_high_down = _is_high_vol & (_trend_sum <= 0)

buckets_full = pd.Series("low_vol", index=prices.index)
buckets_full[_high_up] = "high_vol_up"
buckets_full[_high_down] = "high_vol_down"


def bucket_occupancy(start, end):
    """
    Fraction of the calendar test block [start, end) spent in each bucket,
    from the regime_1p5 classification. Bucketing is identical across up_mult
    -- only the size inside high_vol_up differs -- so one occupancy table
    describes both regime variants.

    Slices the finished full-history label series with the same half-open
    mask evaluate_block uses. (backtest() drops the block's first row, since
    pct_change() makes it NaN, so it evaluates one day fewer than this
    counts. The difference is one day out of ~375 and does not move a
    fraction meaningfully.)
    """
    mask = (buckets_full.index >= start) & (buckets_full.index < end)
    block = buckets_full[mask]          # <-- slice, never reclassify
    counts = block.value_counts()
    return {label: (int(counts.get(label, 0)), int(counts.get(label, 0)) / len(block))
            for label in BUCKET_LABELS}


def verdict_line(tag, question, challenger, baseline, sharpes):
    """One labelled head-to-head Sharpe verdict. Ties go to the baseline --
    the burden of proof is on the challenger."""
    a, b = sharpes[challenger], sharpes[baseline]
    winner = challenger if a > b else baseline
    return (f"  [{tag}] {question:14s} {challenger} vs {baseline}: "
            f"Sharpe {a:6.3f} vs {b:6.3f}  ->  {winner:10s} ({a - b:+.3f})")


# --- Run -----------------------------------------------------------------
folds = build_folds(prices.index, MIN_TRAIN_YEARS, TEST_MONTHS, STEP_MONTHS)

print(f"Phase 2 -- three-bucket regime switch on {TICKER}, "
      f"Phase 1 walk-forward harness.")
print(f"{MIN_TRAIN_YEARS}y minimum anchored train window, {TEST_MONTHS}-month "
      f"non-overlapping test blocks, {COST_BPS:.0f} bps one-way costs.")
print(f"Sizing base k={K} / {LOOKBACK}d. Regime switch: trend_window="
      f"{TREND_WINDOW}, vol_percentile={VOL_PERCENTILE}, "
      f"vol_lookback={VOL_LOOKBACK}, down_floor={DOWN_FLOOR}.")
print(f"Full history: {prices.index.min().date()} -> "
      f"{prices.index.max().date()} ({len(prices)} days), {len(folds)} folds.\n")

for fold_number, (train_start, train_end, test_start, test_end) in enumerate(folds, start=1):
    print(f"=== Fold {fold_number} ===")
    print(f"  Train (in-sample):     {fmt_span(prices, train_start, train_end)}")
    print(f"  Test  (OUT-of-sample): {fmt_span(prices, test_start, test_end)}")
    print()

    print(f"  {'Strategy':11s} {'CAGR':>9s} {'Vol':>8s} {'Sharpe':>8s} "
          f"{'MaxDD':>9s} {'Turnover':>9s}")

    fold_sharpes = {}
    for name, positions_full in strategies_full.items():
        results, m = evaluate_block(prices, positions_full,
                                    test_start, test_end, COST_BPS)
        fold_sharpes[name] = m["Sharpe"]

        # Turnover, not trade count -- these are continuous-position
        # strategies, so trade count understates churn (see CLAUDE.md).
        total_turnover = results["turnover"].sum()
        print(f"  {name:11s} {m['CAGR']:9.2%} {m['Volatility']:8.2%} "
              f"{m['Sharpe']:8.3f} {m['Max drawdown']:9.2%} "
              f"{total_turnover:9.2f}")

    # SEPARATE questions. Kept apart on purpose -- see module docstring.
    # A/B are the original two; C/D/E decompose the architecture into its
    # defensive half (the down-cut) and its offensive half (the up-lever),
    # using regime_1p0 as the control that neutralises the up-lever.
    print()
    print(verdict_line("A", "ARCHITECTURE",  "regime_1p5", "vol_scaled", fold_sharpes))
    print(verdict_line("B", "AGGRESSION",    "regime_2p0", "regime_1p5", fold_sharpes))
    print(verdict_line("C", "DOWN-CUT ONLY", "regime_1p0", "vol_scaled", fold_sharpes))
    print(verdict_line("D", "UP-LEVER 1.5",  "regime_1p5", "regime_1p0", fold_sharpes))
    print(verdict_line("E", "UP-LEVER 2.0",  "regime_2p0", "regime_1p0", fold_sharpes))

    # Required diagnostic: where did this fold's days actually sit?
    occupancy = bucket_occupancy(test_start, test_end)
    total_days = sum(count for count, _ in occupancy.values())
    print(f"\n  Regime occupancy (regime_1p5 classification, "
          f"{total_days} test-block days):")
    for label in BUCKET_LABELS:
        count, fraction = occupancy[label]
        print(f"    {label:14s} {count:4d} days  {fraction:6.2%}")
    print()

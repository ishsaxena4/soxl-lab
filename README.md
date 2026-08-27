# Quantitative Analysis and Strategy on Semiconductor ETFs

An educational systematic-trading research project built around the leveraged
semiconductor ETFs **SOXL** (3x long) and **SOXS** (-3x short).

The goal is **learning** — understanding leveraged-ETF mechanics, volatility
decay, regime detection, and honest backtesting from the ground up. Every
component is written from scratch and understood line by line rather than
pulled from a framework. Profit is a measurement signal, not the objective.

> **This is research code, not financial advice, and not production trading
> infrastructure.** Nothing here is deployed with real money. Backtest results
> describe the past; they are not predictions of future returns, and that
> caveat is especially sharp for leveraged ETFs.

---

## The thesis

Leveraged ETFs like SOXL target a multiple of the underlying index's **daily**
return, then rebalance every day. Over any horizon longer than one day, returns
are **path-dependent** — the outcome depends on the whole return path, not just
where the index started and ended.

The consequence is **volatility decay**. For a daily-rebalanced βx fund the drag
is roughly `½·β·(β−1)·σ²` per unit time, scaling with the *variance* of daily
returns. For β=+3 that coefficient is 3σ²; for β=−3 it's 6σ², so the inverse
fund bleeds faster. Semiconductors are volatile, so this term is large.

But it cuts both ways: chop punishes these funds, while smooth trends *amplify*
in their favor. SOXL can beat 3x the index in a trending year and badly lag it
in a choppy one.

**So the bet this project makes is not on direction.** Predicting direction is
crowded and latency-disadvantaged for a retail participant. The bet is on
**regime classification** — be in the funds when the tape trends, be flat when
it grinds sideways. "No trade" is treated as a first-class output.

---

## What's built

| Module | Scope | Status |
|---|---|---|
| 0 | Instrument mechanics — daily reset, decay, path dependency | Done (conceptual) |
| 1 | Data — daily history for SOXL/SOXS/SOXX, measured decay vs. naive "3x" | Done |
| 2 | Backtest engine — realistic costs, no look-ahead, validated on trivial strategies first | Done |
| 3 | Features & regime detection | **Active** — Phase 1 done, Phase 2 implemented, not yet evaluated |
| 4 | Modeling & evaluation (simple models before neural, walk-forward OOS) | Not started |
| 5 | Risk & sizing (loss limits, fractional-Kelly at most) | Not started |
| 6 | Paper loop → tiny real capital | Not started |

### Module 1 — Data

`src/data.py` exposes `get_prices()`, returning daily adjusted closes for SOXL,
SOXS, and SOXX (the iShares semiconductor ETF, used as a tradeable index proxy).

The data window is **pinned and cached** — `FROZEN_END = "2026-07-15"`, cached
to `data/prices.csv` — so metrics stay stable across a multi-day work session
instead of drifting every time a new trading day appends to the feed. Roll the
window forward deliberately with `get_prices(force_refresh=True)`.

### Module 2 — Backtest engine

`src/backtest.py`:
- `backtest()` — positions are shifted one day forward against asset returns, so
  a position decided from today's close can only earn *tomorrow's* return. A
  5 bps one-way cost model is charged on turnover, compounded into an equity curve.
- `metrics()` — CAGR, annualized volatility, Sharpe, max drawdown, trade count.

`src/strategy.py` implements the regime strategies: `vol_filter_positions`,
`momentum_filter_positions`, `combined_filter_positions`, and the incumbent
`vol_scaled_positions` (continuous sizing, `k / realized_vol` clipped to `[0, 1]`).

### Module 3, Phase 1 — Walk-forward harness

`src/walkforward.py` runs an anchored (expanding-window) walk-forward on SOXL:
train windows anchored at 2015-01 with a 5-year minimum, non-overlapping 18-month
test blocks, yielding 4 complete folds from 2020-01 to 2026-01.

A **continuity guard** matters here: positions are computed once on the full
price history and then *sliced* per fold, never recomputed inside a fold. A cold
rolling-window restart would leave each fold's first ~20 days underfilled, and
`.fillna(0.0)` would silently turn that into a fake "flat" opening. Slicing a
finished backward-looking series is not look-ahead.

---

## Headline result

Vol-scaled sizing (`lookback=20`, `k=0.60`) vs. buy-and-hold, out-of-sample:

| Fold | Test span | Regime | VS Sharpe | B&H Sharpe | VS MaxDD | B&H MaxDD | Winner |
|---|---|---|---|---|---|---|---|
| 1 | 2020-01 → 2021-07 | COVID crash + recovery | 1.163 | 1.061 | −44.3% | −80.4% | **VS** |
| 2 | 2021-07 → 2022-12 | 2022 grind-down | −0.104 | −0.302 | −63.8% | −90.5% | **VS** |
| 3 | 2023-01 → 2024-07 | bull rip | 1.748 | 1.848 | −40.8% | −49.0% | **B&H** |
| 4 | 2024-07 → 2025-12 | choppy/down | 0.316 | 0.414 | −69.3% | −87.9% | **B&H** |

**2/4 on Sharpe — but perfectly regime-sorted.** Vol-scaling wins both crash
folds and loses both calm/bull folds. That's a mechanism, not a coin flip.

**The honest characterization: this is crash insurance, not broad alpha.** The
product is risk, not return — max drawdown is roughly halved in every single
fold. The thin whole-cycle Sharpe edge (+0.024 full-sample) is decisive crash
wins netted against a bull-market premium the strategy pays *by design*: sizing
down in high-vol-up regimes caps upside. Fold 3 gave up ~87 points of CAGR
(147% vs. 233%). Crash protection and forfeited bull upside are the same coin.

Its blind spot is a sudden, un-signalled V-crash. A trailing-vol signal cannot
react to a discontinuity — in COVID it protected capital (−44% vs −80%) but lost
on Sharpe. **That blind spot is a fundamental cost of using realized, lagging
information, not a bug to be patched.**

This was also corroborated two other ways: a SOXL train/test split
(`src/split_test.py`) where drawdown protection held in *both* halves, and a
synthetic 3x-QQQ series back to 1999 (`src/qqq_test.py`) where vol-scaling
roughly halved volatility and reduced drawdown across all four major crises
(dot-com, GFC, COVID, 2022), improving Sharpe in three of the four.

---

## Where things stand

**Module 3, Phase 2 is written but not yet evaluated.** `regime_switch_positions`
in `src/strategy.py` implements a three-bucket regime switch that tries to
recover the bull-market upside vol-scaling forfeits:

1. low vol → size exactly like plain vol-scaling
2. high vol **and** trend up → size *above* vol-scaling (`up_mult · k / v`)
3. high vol **and** trend down → flat

The hard constraint is **reactive, never predictive** — classify the regime
currently in progress, never forecast the turn.

`src/phase2_run.py` runs this through the Phase 1 folds against three settings
of the aggression knob, deliberately keeping the defensive half (the down-cut)
and the offensive half (the up-lever) attributable separately rather than
merging them into one win/loss. **Those results have not been recorded yet — that
is the next concrete step.**

---

## Repo layout

```
soxl-lab/
├── CLAUDE.md          # full project context, roadmap, working conventions
├── TEACHING.md        # how I want to be taught on this project (method, not state)
├── requirements.txt
├── data/              # cached pulls — gitignored, never committed
├── notebooks/         # exploration
└── src/
    ├── data.py          # price loading, pinned window, caching
    ├── backtest.py      # backtest() + metrics()
    ├── strategy.py      # all position-sizing strategies
    ├── walkforward.py   # Module 3 Phase 1 — anchored walk-forward harness
    ├── phase2_run.py    # Module 3 Phase 2 — regime switch through the harness
    ├── split_test.py    # Module 2 — one-shot train/test split
    ├── qqq_test.py      # Module 2 — synthetic 3x-QQQ, 1999–2026
    └── yearly.py        # year-by-year decay table
```

`CLAUDE.md` is the fullest account of the project — state, results, and the
methodological lessons banked along the way.

## Setup

```bash
pip install -r requirements.txt
```

## Running it

Each script is standalone. Run from inside `src/` so the sibling imports resolve:

```bash
cd src

python data.py         # load prices + print the yearly SOXL-vs-3x-SOXX decay table
python backtest.py     # engine sanity check: buy-and-hold on SOXL
python strategy.py     # all strategies compared side by side, full sample
python walkforward.py  # Phase 1 walk-forward — reproduces the table above
python phase2_run.py   # Phase 2 regime switch across the same folds
python split_test.py   # train/test split validation
python qqq_test.py     # synthetic 3x-QQQ across four crises
```

The first run pulls from yfinance and caches to `data/`; later runs read the cache.

---

## Conventions worth knowing

A few rules this repo holds itself to, learned the hard way:

- **No look-ahead, ever.** Information from `t+1` never reaches a decision made
  at `t`. Anything that risks it gets flagged in a comment.
- **Costs are not optional.** A backtest without spread and fees is a lie.
- **Trade count is meaningless for continuous-position strategies** — measure
  total turnover instead.
- **Returns are multiplicative**, so year-over-year edge is measured in log
  terms, never summed arithmetically.
- **Measure a problem before building machinery to fix it.**
- **Risk is framed as loss limits, never profit targets.** A profit target
  encourages overtrading and revenge-sizing; a loss limit protects capital.

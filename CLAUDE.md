# CLAUDE.md — soxl-lab

Context file for Claude Code. Read this before doing anything in this repo.

---

## 1. What this project is

`soxl-lab` is an **educational** systematic-trading and machine-learning project
built around the leveraged semiconductor ETFs **SOXL** (3x long) and **SOXS**
(-3x short). The primary goal is **learning** — understanding intraday mechanics,
volatility decay, regime detection, backtesting, and ML-in-finance from the ground
up. Profit is a secondary measurement signal, not the objective.

This is a personal learning project owned by a student studying AI + Mathematics
who is targeting quant / ML-in-finance work. Treat the human as the architect and
yourself as the executor (see Section 2 — this is the most important section).

**This is not** production trading infrastructure and **not** financial advice.
No real money is deployed until a strategy has passed backtesting AND forward
paper-trading. Assume everything is research and paper trading unless told otherwise.

---

## 2. How to work with the human (read this carefully)

The human is deliberately learning this domain. The point is for **them** to
understand every part of the system, not to receive a finished black box. Your job
is to be fast hands and an on-demand tutor — never the brain.

**Rules:**

- **Do exactly what is asked — no more.** Do not run ahead and build modules,
  features, or files that weren't requested. If you think a next step is valuable,
  *suggest* it and wait. Scope creep robs the human of the reasoning.
- **Explain, don't just deliver.** When you write or change code, briefly explain
  what it does and why. If the human asks "what does this line do," give a clear,
  concrete answer at the level of a smart student, not a hand-wave.
- **No unexplained magic.** Avoid clever one-liners the human can't read. Prefer
  clear, well-named, commented code over compact code. Readability > brevity here.
- **Flag assumptions.** If a task is ambiguous, ask or state your assumption
  explicitly rather than guessing silently.
- **Surface the "why."** When there's a design choice (a library, a data source, a
  method), name the tradeoff so the human can decide, rather than deciding for them.
- **The human closes the loop elsewhere.** After you produce output, the human takes
  it to a separate teaching conversation to interpret it. So make your output easy
  to read and reason about — clear prints, labeled tables, sensible variable names.

If you ever catch yourself producing code the human couldn't re-explain from
scratch, stop and explain it first.

---

## 3. Domain background you must know

**Leveraged ETF mechanics (the core fact):**
SOXL/SOXS target a *multiple of the underlying index's DAILY return*, then rebalance
each day. Over any horizon longer than one day, returns are **path-dependent** — the
result is a function of the whole return path, not just the index's start and end.

**Volatility decay:** In choppy/sideways markets, both the long and inverse funds
lose value even if the index goes nowhere. The drag on a daily-rebalanced βx fund is
approximately `½·β·(β−1)·σ²` per unit time — it scales with the **variance** of daily
returns. For β=+3 the coefficient is 3σ²; for β=−3 it's 6σ² (the inverse fund decays
faster). Semiconductors are highly volatile, so this term is large and dominant.

**The two-sided coin:** Decay punishes these funds in chop, but trends *amplify* in
their favor (compounding works for you in a smooth trend). So SOXL can beat 3x the
index in trending years and badly lag it in choppy years.

**The central thesis of this project:** The edge is NOT predicting direction (that's
crowded and latency-disadvantaged for a retail participant). The edge is
**regime classification** — be in the funds when the tape is trending, be FLAT when
it's grinding sideways. "No trade" is a first-class, valuable output. Everything
downstream (features, models, sizing) ultimately serves this one call.

**Underlying index:** SOXL/SOXS track a specific semiconductor index; confirm the
exact current index from the Direxion prospectus before relying on it. `SOXX`
(iShares Semiconductor ETF) is used as a close, tradeable proxy for early analysis.

---

## 4. Architecture / module roadmap

Build in this order. Do not skip ahead or pre-build later modules.

- **Module 0 — Instrument mechanics** *(done, conceptual)*: daily-reset math,
  volatility decay, path-dependency, the regime thesis.
- **Module 1 — Data** *(current)*: pull and sanity-check daily history for SOXL,
  SOXS, and an index proxy (SOXX). Measure actual historical decay vs. the naive
  "Nx" assumption, year by year.
- **Module 2 — Backtest engine**: built from scratch and understood line by line.
  Realistic costs (spread, fees), no look-ahead bias. Validated first on trivial
  strategies (buy-and-hold) before anything clever.
- **Module 3 — Features & regime detection**: volatility-state / regime features
  first (the real edge); sentiment + fundamentals second, grounded in hard data
  (earnings, guidance, analyst revisions, implied vol / skew).
- **Module 4 — Modeling & evaluation**: simple models first (logistic regression,
  gradient boosting) before anything neural. Walk-forward out-of-sample testing.
  Judge on Sharpe and max drawdown, not raw P&L.
- **Module 5 — Risk & sizing**: daily loss limits (not profit targets),
  fractional-Kelly-at-most sizing, hard per-trade stops.
- **Module 6 — Paper loop → tiny real capital**: forward paper-trade until there's a
  statistically meaningful sample, then deploy only an amount that's fine to lose.

---

## 5. Tech stack & conventions

- **Language:** Python 3.
- **Core libs:** `yfinance`, `pandas` (add `numpy`, `matplotlib`,
  `scikit-learn` as later modules require — but only when a module needs them).
- **Repo structure:**
  ```
  soxl-lab/
  ├── CLAUDE.md            # this file
  ├── requirements.txt
  ├── .gitignore           # ignores data/ and the venv
  ├── README.md
  ├── data/                # cached pulls — gitignored, never commit raw data
  ├── notebooks/           # exploration
  └── src/                 # reusable code (data.py, backtest.py, etc.)
  ```
- **Separation of concerns (important for later):** keep a **deterministic,
  backtestable signal layer** strictly separate from any **LLM / annotation layer**.
  Signals must be reproducible without any model calls.
- **No look-ahead bias — ever.** Never let information from time `t+1` leak into a
  decision made at time `t`. Flag anything that risks this.
- **Realistic costs.** Backtests must model spread, fees, and (for multi-day holds)
  decay. A backtest without costs is a lie; say so if asked to omit them.
- **Reproducibility.** Set random seeds where relevant. Cache data pulls to `data/`
  so results are stable across runs.
- **Trade count is meaningless for continuous-position strategies** — measure
  total turnover instead.
- **Git habit:** commit after each working step with clear messages
  (e.g. `scaffold repo`, `add data loader`). Small, frequent commits.
- **Keep §7 current automatically.** After finishing a module milestone (or a
  meaningful step within one), update Section 7 — Current status in this same
  turn, without being asked. It should always state which module is done, which
  is active, and what the next concrete step is.

---

## 6. Guardrails

- Educational and paper-first. No real-money trading logic gets deployed until a
  strategy passes backtest + forward paper trading.
- Do not present backtest results as predictions of future returns. Past
  performance, especially on leveraged ETFs, is not indicative of future results.
- Frame risk in terms of **loss limits**, never daily profit targets. A profit
  target encourages overtrading and revenge-sizing; a loss limit protects capital.
- The human is not a licensed financial advisor and neither are you. This code is
  for learning market mechanics and systematic-research process.

---

## 7. Current status

**Module 1** (data) is done: `src/data.py` exposes `get_prices()`, which loads
daily adjusted closes for SOXL/SOXS/SOXX. The data window is now **pinned and
cached**: `FROZEN_END = "2026-07-15"` (yfinance's `end` is exclusive, so this
covers every close through 2026-07-14) and results are cached to
`data/prices.csv` so metrics stay stable across a multi-day work session instead
of shifting every time a new live trading day appends to the feed. Call
`get_prices(force_refresh=True)` and update `FROZEN_END` to deliberately roll
the window forward. Run as a script it also prints the yearly SOXL-vs-3x-SOXX
decay table.

**Module 2** (backtest engine) is **complete**, including out-of-sample
validation. `src/backtest.py` has `backtest()` (positions shifted one day
forward against asset returns — no look-ahead — with a 5 bps one-way cost
model on turnover, compounded into an equity curve) and `metrics()` (CAGR,
annualized vol, Sharpe, max drawdown, trade count). `src/strategy.py`
implements four regime strategies — `vol_filter_positions`,
`momentum_filter_positions`, `combined_filter_positions`, and
`vol_scaled_positions` (continuous sizing, `k / realized_vol` clipped to
`[0, 1]`).

**Incumbent strategy:** `vol_scaled_positions` — 20-day realized-vol window,
`k = 0.60`. Full-sample (SOXL, 2015-01-02 → 2026-07-14): Sharpe 0.917 vs.
buy-and-hold's 0.893, MaxDD −69% vs. −90%, cost drag ~0.23%/yr (negligible —
turnover, not trade count, is the honest cost measure for a continuous-sizing
strategy).

**Validated out-of-sample two ways:**

1. **SOXL train/test split** (`src/split_test.py`). Train 2015–2021:
   buy-and-hold edges vol-scaled on Sharpe (1.018 vs. 0.992). Test 2022–2026:
   vol-scaled wins (0.800 vs. 0.760). Drawdown protection held in *both*
   halves — the edge isn't a single lucky window.
2. **Synthetic 3x-QQQ, 1999–2026** (`src/qqq_test.py`), simulated via
   multiplicative daily-reset compounding on QQQ's own return history, with
   `k` re-anchored to QQQ's own average vol (not SOXL's). Vol-scaled cut
   volatility roughly in half and reduced drawdown across all four crises
   (dot-com, GFC, COVID, 2022); Sharpe improved in three of four.

**Honest characterization:** this is **crash insurance, not broad alpha**. It
pays a premium in calm bull markets and collects in crises. Its blind spot is
a sudden, un-signalled V-crash (2020, COVID) — a trailing-vol signal can't
react to a discontinuity, so it protects capital there (drawdown −35% vs.
−70%) but loses on Sharpe. **This blind spot is a fundamental cost of using
realized (lagging) information, not a bug to patch.**

**Key methodological lessons banked** (carry these into every future module):
- Trade count is meaningless for continuous-position strategies — always
  measure total turnover instead.
- Returns are multiplicative, so year-by-year edge must be measured in **log**
  terms, not summed arithmetically.
- Measure a problem before building machinery to fix it.
- Verify Claude Code's implementation actually matches the spec — it has
  previously substituted a moving-average crossover for a rolling-sum
  calculation, and once corrupted a file via interleaved edits. Read the diff.

**Module 3** (features & regime detection) is now active. Plan, in order:

1. Build a **walk-forward out-of-sample harness first**, so every feature and
   strategy added from here on is judged on unseen data by construction —
   Module 2's split test was a one-shot proof of concept, not the final
   harness. **Phase 1 complete.**
2. Then add **directional regime features one at a time**, each with a
   stated mechanism and a named failure mode, validated before the next is
   added.
3. All of this sits on top of vol-scaling as the sizing layer underneath —
   the goal is to add directional edge on top of the crash-insurance base,
   not replace it.

**Phase 1 — `src/walkforward.py` — BUILT, RUN, AND INTERPRETED.** Anchored
(expanding) walk-forward on SOXL comparing `vol_scaled_positions`
(`lookback=20`, `k=0.60`) against buy-and-hold, 5 bps one-way costs, all reused
from `data.py` / `backtest.py` / `strategy.py`. Train windows anchored at
2015-01 (2018 crash in every train window), 5-year minimum; test blocks 18
months, non-overlapping (step = test length), yielding **4 complete folds**
(2020-01 → 2026-01).

*Continuity guard:* positions computed **once on full price history**
(`vs_positions_full = ...` under the `***** CONTINUITY GUARD *****` banner)
and **sliced** per fold in `evaluate_block()` — never recomputed inside a
fold. A cold rolling-window restart would make each fold's first ~20 days
NaN/underfilled, which `.fillna(0.0)` would silently turn into a fake "flat"
opening. Slicing a finished backward-looking series is not look-ahead.

**Results** (vol-scaled vs buy-and-hold, out-of-sample):

| Fold | Test span | Regime | VS Sharpe | B&H Sharpe | VS MaxDD | B&H MaxDD | Winner |
|------|-----------|--------|-----------|------------|----------|-----------|--------|
| 1 | 2020-01→2021-07 | COVID crash + recovery | 1.163 | 1.061 | −44.3% | −80.4% | **VS** |
| 2 | 2021-07→2022-12 | 2022 grind-down | −0.104 | −0.302 | −63.8% | −90.5% | **VS** |
| 3 | 2023-01→2024-07 | bull rip | 1.748 | 1.848 | −40.8% | −49.0% | **B&H** |
| 4 | 2024-07→2025-12 | choppy/down | 0.316 | 0.414 | −69.3% | −87.9% | **B&H** |

**Verdict: 2/4 on Sharpe, but perfectly regime-sorted.** Vol-scaling wins both
crash folds, loses both calm/bull folds — not a coin flip, a mechanism. This
confirms out-of-sample what Module 2 characterized: vol-scaling is a
**regime-conditional drawdown-control layer, not broad alpha**. The product is
risk, not return — MaxDD is roughly halved in every fold. The thin
whole-cycle Sharpe edge (+0.024 full-sample) is decisive crash wins netted
against a bull-market premium the strategy pays *by design*: sizing down in
high-vol-up regimes caps upside (Fold 3 gave up ~87 pts of CAGR, 147% vs
233%). Crash protection and bull-upside forfeit are the same coin — cost
accepted with eyes open. Vol-scaling is carried forward as Module 3's sizing
layer.

**Open items carried into Phase 2:**
- *Train window is still inert.* `vol_scaled_positions` fits nothing —
  `k=0.60` is a hard-coded constant, not estimated from train data — so the
  expanding train window is reported but never consumed. The scaffolding is
  correct and necessary for Phase 2 (fitted features/models); for Phase 1 the
  "out-of-sample" claim rests only on disjoint test blocks, not on any
  fit/predict separation. `k` was also chosen with full-sample knowledge.
- *Fold-boundary entry cost.* `backtest()` starts each slice from a flat book
  (`positions.shift(1).fillna(0.0)`), so every fold charges a one-off ~5 bps
  entry on its first traded day, buy-and-hold included. Tiny and symmetric, an
  artifact of slicing not real trading. Same as `split_test.py`; left as-is.
- *~6 months unused.* The post-2026-01 tail is shorter than a full 18-month
  block and dropped, so a noisier stub fold can't get an equal vote.

**Phase 2 — directional regime features (next, not yet started).** Target:
classify the **sign** of the current volatility regime (high-vol-up vs
high-vol-down) from present/past evidence only, so sizing can stay big in
up-turbulence and shrink in down-turbulence — recovering the bull-market
upside vol-scaling forfeits, without losing crash protection. **Hard
constraint: reactive, never predictive** — classify the regime currently in
progress, never forecast the turn. Build one feature at a time, each with a
stated mechanism and a named failure mode, validated on the walk-forward
harness before the next is added.

Next concrete step: begin Phase 2 — design the first directional (vol-sign)
feature, starting by naming the market condition where it misleads before
building it.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

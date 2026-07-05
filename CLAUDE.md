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
- **Git habit:** commit after each working step with clear messages
  (e.g. `scaffold repo`, `add data loader`). Small, frequent commits.

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

Between **Module 0** (complete, conceptual) and **Module 1** (data). Immediate task:
scaffold the repo, write `src/data.py` to download daily adjusted closes for
SOXL/SOXS/SOXX since 2015, compute daily returns, and produce a yearly table
comparing SOXL's actual return to 3× SOXX's return (to measure real decay vs.
trend-amplification). Keep it to that scope.

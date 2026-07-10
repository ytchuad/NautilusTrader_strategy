# CryptoQuant AI — Volume Profile + CVD Orderflow Backtest

A systematic orderflow strategy for BTCUSDT perpetual futures, using **Volume Profile** (POC/VAH/VAL) and **CVD divergence** (absorption/exhaustion) with dynamic position sizing. Built and backtested on real Binance market data.

---

## Data Sources

| Source | Type | Description |
|--------|------|-------------|
| **Binance aggTrades** | Tick trades | `transact_time`, `price`, `quantity`, `is_buyer_maker` |
| **Binance bookTicker** | L1 quotes | `transaction_time`, `best_bid/ask_price/qty` (sampled 1:50) |

- Symbol: `BTCUSDT` (perpetual futures, `um` market)
- Precision: price = 1 (tick = 0.1), size = 3
- Daily volume: ~4M rows aggTrades (50MB zipped), ~25M rows bookTicker (300MB zipped)
- Download via [Binance Public Data](https://data.binance.vision)

---

## Notebooks

| Notebook | Description |
|----------|-------------|
| `profile_orderflow_strategy_v11.ipynb` | **Active strategy** — v11: 3 active setups, relaxed VAH_RECLAIM CVD, candidate diagnostics |
| `profile_orderflow_strategy_v11_executed.ipynb` | Same as above with all outputs pre-executed |
| `profile_orderflow_strategy.ipynb` | v10 reference (production rules, 4 setups) |
| `profile_orderflow_strategy_executed.ipynb` | v10 executed reference |
| `btcusdt_orderflow_backtest.ipynb` | First orderflow prototype (reference only) |
| `backtest_visualization.ipynb` | EMA cross reference backtest |

---

## Strategy Evolution

### v1–v5: Initial Development
- Raw Volume Profile calculator
- EMA cross and OrderBookImbalance prototypes
- Caching and data pipeline setup

### v6 — VAL/VAH Mean-Reversion (Mar 9–15 test window)
- **Entry**: Long at prior day **VAL** (with CVD absorption), Short at prior day **VAH** (with CVD exhaustion)
- **Composite profile**: 5-day background (Mar 4-8) for bias filter
- **Results**: 12 trades, 0% win rate on shorts, **no longs triggered** (price never retraced to VAL during the uptrend)

### v7 — POC Reversal/Continuation
- **Entry**: Both directions at prior day **POC**
- **Direction**: CVD divergence decides — absorption → LONG, exhaustion → SHORT
- **Targets**: prior day VAH (longs) / VAL (shorts)
- **No composite bias filter** — CVD alone determines direction
- **Results**: 11 trades (6L/5S), −6.33% total, 18% win rate

---

## Key Components

### Volume Profile Calculator
```
Bucket price × tick → groupby sum volume → POC → expand 70% of total volume → VAH/VAL
```
- Single-day and composite (multi-day) profiles supported
- Computation: ~23s for 5 days of full aggTrades (~16M rows)

### CVD Divergence Detection
```
Absorption (bullish):  price MAKES NEW LOW but CVD does NOT → reversal up
Exhaustion (bearish):  price MAKES NEW HIGH but CVD does NOT → reversal down
```
- CVD = Cumulative Delta (buy volume − sell volume per bar)
- Lookback: 5 minute-bars for recent context

### Entry Logic (v11)
```
VAH Reclaim Breakout (LONG):
  Close ≥ prior VAH, CVD bullish OR (not falling AND not bearish), 0.5×ATR buffer
  Target: +1R (50%), +2R (30%), runner trail

VAL Rejection Mean-Reversion (LONG):
  Close in value area near VAL, CVD recovery confirmed, delta bullish, imbalance
  Target: prior POC

VAH Rejection Mean-Reversion (SHORT):
  Close in value area near VAH, CVD bearish OR failed recovery, delta bearish, imbalance
  Target: prior POC
```

### Dynamic Position Sizing
```
Setup risk:  VAH_RECLAIM_LONG=1%, VAL_REJECTION_LONG=1%, VAH_REJECTION_SHORT=0.75%, VAL_RETEST_FAILURE_SHORT=0.5%
Position (BTC) = Account × setup_risk ÷ ATR
Cap: max 3× notional leverage, max 5 BTC
```
- Stop: entry − 1× ATR for longs, entry + 1× ATR for shorts
- Breakeven at 0.5× ATR
- Runner trail at 0.5× R after +2R target hit

### Profile Sources
- **Composite**: 5 trading days (Mar 4-8) — for market context only
- **Prior day**: single-day VAL/VAH/POC — for entry trigger levels
- **Stale profile detection**: weekend gap (>1 day), open gap >0.4%, or gap >1× ATR
- **Rolling 24h fallback**: when stale, fallback to last 24h of aggTrades
- Test window: Mar 11-22 (10 days), extended to 1 month in v12

---

## Results (v7)

```
Total: 11 trades
  Longs: 6 | Shorts: 5
  Wins: 2/11 (18%)
  Total PnL: −6.33% (−6328 USDT)
  Avg per trade: −0.575%
  Long PnL: −4.85%
  Short PnL: −1.48%
```

### Main Issues Identified
1. **POC whipsaw** — 2% fixed stop too tight for POC entries (price oscillates around POC). Mar 12 alone: 5 sequential long stops hit in the 71900–72100 zone.
2. **No re-entry cooldown** — Persistent CVD divergence fires repeatedly, causing multiple small losses in the same area.
3. **Trend vulnerability** — Trending days (e.g., Mar 11 uptrend, Mar 13 uptrend) produce consecutive stopped-out reversals.

---

---

## Results (v11) — Candidate Diagnostics (Mar 11–22)

### Strategy Changes from v10
- **Disabled VAL_RETEST_FAILURE_SHORT** — was 1/4 wins, −$1,067
- **Relaxed VAH_RECLAIM_LONG CVD logic**: passes if `_cvd_bullish()` (30-bar uptrend) OR (`_cvd_not_falling()` AND not `_cvd_bearish()`)
- **New `_cvd_not_falling()`**: checks CVD stable/rising over last 5–10 bars
- **Fixed day 1 fallback**: pre-cached 2024-03-10 aggTrades for first test day
- **Candidate diagnostics**: per-setup funnel tracking showing % drop-off at each filter stage

### Results

```
Total: 10 trade legs (10 distinct entries)
  Wins:  7/10 (70%)
  Total PnL: +2.03% (+2,032 USDT)
  Avg win: 0.18% | Avg loss: −0.18%
  Avg lev: 1.96x | Max lev: 2.69x
  Max single loss: −583 USDT | Max single win: +1,642 USDT

VAL_REJECTION_LONG:    7 legs, +521 USDT (5/7 wins)
VAH_REJECTION_SHORT:   3 legs, +1,511 USDT (2/3 wins)
VAH_RECLAIM_LONG:      0 legs (still never triggered)
```

### Candidate Diagnostic Funnel

```
VAH_RECLAIM_LONG (13,918 candidates → 0 entered):
  CVD OK:       44%  (relaxed logic helped)
  State OK:     13%  (rarely confirmed above VAH)
  Delta OK:      6%
  Overextended:  0.1% ← KILLER: 98% of state-confirmed bars blocked by >VAH+ATR check

VAL_REJECTION_LONG (13,915 candidates → 7 entered):
  CVD recovery:  8%  (main signal bottleneck — intentional)
  Setup disabled:48%  (1-entry/day + failure flag)

VAH_REJECTION_SHORT (13,918 candidates → 3 entered):
  Target dist:   8%  (POC often too close to VAH)
  Setup disabled:25%  (failure flag blocks rest of day)
```

### Key Findings
1. **VAH_RECLAIM_LONG overextension filter is bugged for breakouts**: `entry > active_VAH + ATR` blocks 98% of state-confirmed bars — being above VAH + ATR is expected for a breakout, not overextended
2. **Day 1 rolling 24h fallback works** — Mar 11 now has 1 trade vs 0 in v10
3. **VAL rejection dominates volume** — 7/10 legs, but small PnL per trade (avg +$74)
4. **VAH rejection produces the best risk-adjusted trades** — 3 legs averaging +$504 per win

---

## Future Plans

### Short-term Fixes (next iteration)
- [x] **Re-entry cooldown**: Block re-entries for N bars after a stopped-out trade (v8)
- [x] **ATR-based stops**: ATR-based stop buffers on breakout trades (v8, 0.5× ATR buffer at VAL/VAH acceptance level)
- [x] **Trailing stop**: Runner trail at 0.5× R / 0.5× ATR on breakout trades (v8)
- [x] **Additional data window**: Extended to 10 trading days (Mar 11-22) in v9
- [x] **Max position size cap**: Limit notional leverage to prevent 10+ BTC positions (v10, 3× max, 5 BTC max)
- [x] **Weekend gap handling**: Adjust prior-day profile relevance after weekends (v10, stale detection + rolling 24h)
- [x] **Stronger divergence filter**: Require bar close near extreme or minimum CVD gap (v10, CVD recovery/failed-recovery/extreme)
- [x] **VAL breakdown removal or fix**: This entry type is a consistent loser (v10, replaced with VAL retest-failure + CVD failed recovery)
- [x] **VAH_RECLAIM_LONG CVD relaxed**: Added _cvd_not_falling + bearish check as alternative to _cvd_recovery (v11)
- [x] **VAL_RETEST_FAILURE_SHORT removed**: Was 1/4 wins, −1,067 USDT (v11)
- [x] **Day 1 fallback**: Pre-cache previous day's aggTrades for first test day (v11)
- [ ] **Fix VAH_RECLAIM_LONG overextension**: Breakout shouldn't be blocked by "entry > VAH + ATR"
- [ ] **Extend test window**: Validate on 1+ month of data

### Mid-term Improvements
- [ ] **Multi-timeframe profile**: Use intraday profiles (e.g., Asian/London/NY sessions) alongside daily
- [ ] **Machine learning filter**: Classify high-probability vs. low-probability divergence signals
- [ ] **Dynamic level selection**: Weight prior-day levels by volume or regime recency

### Long-term Goals
- [ ] **Real-time trading**: Connect to Binance WebSocket for live data
- [ ] **Portfolio-level risk**: Multi-asset position sizing and correlation management
- [ ] **Execution algo**: TWAP/Iceberg integration for slippage control
- [ ] **Walk-forward optimization**: Robust parameter selection with out-of-sample validation

---

## Requirements

```txt
pandas>=2.0
numpy
requests
nautilus_trader       # for instrument definition only
```

Install: `pip install -r requirements.txt`

---

---

## Results (v8) — Value Boundary on 5 Test Days (Mar 11–15)

### Strategy Logic
- **No raw POC entry** — only trade at value boundaries (VAL/VAH)
- **CVD regime filter** — 30-bar session-level CVD direction gates all entries
- **Mean-reversion**: VAL rejection (L) → POC target, VAH rejection (S) → POC target
- **Breakout**: VAH reclaim (L) / VAL breakdown (S) → 3-bar confirmation → multi-target exits (+1R 50%, +2R 30%, runner trail)
- **Cooldown**: 5 bars after stop-out, no same-direction re-entry
- **Max trades**: 2 per (level, direction) per day
- **ATR**: 14-bar for stop buffer on breakout trades

### Results

```
Total: 10 trade legs (7 distinct entries)
  Longs:  6 legs | Shorts:  4 legs
  Wins:  6/10 (60%)
  Total PnL: +2.94% (+1,507 USDT)
  Avg win: 0.78% | Avg loss: −0.44%
  Long sum: +3.63% | Short sum: −0.68%
```

### Key Findings
- **VAH reclaim breakout** was the strongest pattern (5/6 winning legs)
- **VAL breakdown** was a consistent loser (0/3)
- **VAL rejection → POC mean-reversion** worked on its only trigger (+0.84%)
- **Cooldown** eliminated the whipsaw sequences seen in v7
- **Multi-target exits** (Mar 11): +1R → +0.67%, +2R → +1.20%, runner → +1.39%

---

## Results (v10) — Production Rules (Mar 11–22)

### Strategy Changes from v9
- **Stale profile detection** — weekend gap and open-gap checks; fallback to rolling 24h profile when stale
- **4 entry setups** — VAH reclaim breakout (L), VAL rejection mean-reversion (L), VAH rejection mean-reversion (S), VAL retest-failure (S)
- **VAH reclaim → LONG breakout** replaces the old VAH reclaim L entry with CVD recovery confirmation
- **VAL retest-failure SHORT** replaces old VAL breakdown — waits for retest of VAL from below + CVD failed recovery
- **Global filters**: min R distance (0.15%), min target distance (0.2%), overextension filter, time window (9:00–23:00 UTC), spread filter (≤25 bps), daily loss limit (2%)
- **Setup-level risk**: 1% / 1% / 0.8% / 0.5% respectively
- **Position caps**: max 3× notional leverage, max 5 BTC
- **Skip logging**: every check logs a skip reason for analysis
- **CVD recovery / failed-recovery / extreme filters** check CVD trajectory relative to price action

### Results

```
Total: 12 trade legs (12 distinct entries)
  Wins:  7/12 (58%)
  Total PnL: +1.01% (+1,009 USDT)
  Avg win: 0.17% | Avg loss: −0.34%
  Avg lev: 1.81x | Max lev: 2.69x
  Max single loss: −592 USDT | Max single win: +1,642 USDT

VAL_REJECTION_LONG:    5 legs, +565 USDT (4/5 wins)
VAH_REJECTION_SHORT:   3 legs, +1,511 USDT (2/3 wins)
VAL_RETEST_FAILURE_SHORT: 4 legs, −1,067 USDT (1/4 wins)
VAH_RECLAIM_LONG:      0 legs (never triggered)
```

### Key Improvements over v9
1. **VAL_REJECTION_LONG flipped from 0/5 to 4/5 wins** — CVD filter + stale detection eliminated bad entries
2. **Win rate 40% → 58%** — stricter filters filter out low-probability setups
3. **Max loss reduced from −1,618 to −592 USDT** — position caps prevented 11 BTC+ sizes
4. **Profile stale detection worked**: 3 days `stale_no_fallback`, 6 days `rolling_24h`, 1 day `prior_daily`
5. **No extreme positioning** — avg lev 1.81x, never exceeded 3x cap

### Remaining Issues
1. **VAL_RETEST_FAILURE_SHORT**: still losing (1/4 wins, −1,067 USDT) — may need removal or tighter filter
2. **VAH_RECLAIM_LONG**: 0 triggers in 10 days — conditions too restrictive (CVD recovery rare in uptrends)
3. **Day 1 (Mar 11)**: 0 trades — no aggTrades cache for rolling 24h fallback on first test day
4. **Top skip reason**: CVD_NOT_CONFIRMED (40% of 44k skips) — suggests CVD filters may be too aggressive

---

## Results (v9) — Extended to 10 Test Days (Mar 11–22)

### Results

```
Total: 20 trade legs (17 distinct entries)
  Longs: 11 legs | Shorts:  9 legs
  Wins:  8/20 (40%)
  Total PnL: +3.25% (−2,788 USDT)
  Avg win: 0.83% | Avg loss: −0.28%
  Long sum: +5.18% | Short sum: −1.93%
  mean_reversion: 4 legs, +2.77% PnL
  breakout: 16 legs, +0.48% PnL
```

*Note: Percentage sum (+3.25%) is unweighted. Actual USD PnL is −2,788 USDT (−2.8% of account) because losing legs had disproportionately large position sizes.*

### Key Problems Exposed
1. **VAL breakdown is a consistent loser** — 0 wins across 7 attempts in 10 days
2. **Position size spikes** — Small R values produce extreme sizes (11.5 BTC on Mar 19 = 8× notional leverage)
3. **Weekend gap** — Mar 15 POC=68000 becomes irrelevant after Mar 18 opens at ~67000
4. **USD PnL vs % PnL divergence** — Unweighted percentage sum masks the true PnL impact

### What Worked
- **VAL rejection → POC mean-reversion**: 3/3 wins on Mar 20
- **VAH reclaim breakout**: strongest pattern across both windows

---

## Reproducing the Backtest

```bash
# Build and run the v11 notebook (active strategy)
python C:\Users\cyt\AppData\Local\Temp\opencode\build_v11.py
jupyter nbconvert --to notebook --execute notebooks/profile_orderflow_strategy_v11.ipynb --output notebooks/profile_orderflow_strategy_v11_executed.ipynb --ExecutePreprocessor.timeout=-1
```

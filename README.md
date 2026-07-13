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
| `profile_orderflow_strategy_v15.ipynb` | **Active strategy** — v15: research-grade rewrite, parquet data, auction context model, 3-category orderflow timing, VAL_REJECTION_LONG primary |
| `profile_orderflow_strategy_v15_executed.ipynb` | Same as above with all outputs pre-executed (18 test days) |
| `profile_orderflow_strategy_v14.ipynb` | v14 reference: 5M bars, fixed CandleBuffer + migration order, 5-state migration, VAL_REJECTION_LONG primary, 15-experiment matrix, 11 CSV exports |
| `profile_orderflow_strategy_v14_executed.ipynb` | Same as above with all outputs pre-executed (18 test days, 15 experiments) |
| `profile_orderflow_strategy_v13.ipynb` | v13 reference: composite bias + dynamic migration, structure stops, range rotation targets, 11-experiment matrix |
| `profile_orderflow_strategy_v13_executed.ipynb` | Same as above with all outputs pre-executed (18 test days, 11 experiments) |
| `profile_orderflow_strategy_v12.ipynb` | v12 reference (VAH_RECLAIM overextension fix, extended test window) |
| `profile_orderflow_strategy_v12_executed.ipynb` | Same as above with all outputs pre-executed |
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

### Entry Logic (v14)
```
VAL Rejection Mean-Reversion (LONG):
  Active setup — composite bias NOT BEARISH, value migration NOT bearish-with-acceptance
  Rejection candle: low touches VAL, close_location>0.50, close inside VA
  3/5 orderflow conditions: delta, imbalance, CVD recovery, absorption, volume
  Structure stop: below rejection_low / active_VAL + min/max distance checks
  Target: POC (40%) → VAH (40%) → runner (20%) if extension eligible

VAH Rejection Mean-Reversion (SHORT):
  Active setup — composite bias NOT BULLISH, value migration NOT bullish-with-acceptance
  Rejection candle: high touches VAH, close_location<0.50, close inside VA
  3/5 orderflow conditions: delta, imbalance, CVD failure, absorption, volume
  Structure stop: above rejection_high / active_VAH + min/max distance checks
  Target: POC (40%) → VAL (40%) → runner (20%) if extension eligible

VAH Reclaim Breakout (LONG):
  DISABLED in v13 — diagnostics only, zero actual trading risk
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
- **Composite**: 5 trading days (Mar 4-8) — now used for directional bias (scored +3 to -3)
- **Prior day**: single-day VAL/VAH/POC — for entry trigger levels
- **Stale profile detection**: weekend gap (>1 day), open gap >0.4%, or gap >1× ATR
- **Rolling 24h fallback**: when stale, fallback to last 24h of aggTrades
- **Dynamic 60M profile**: rolling 60-minute profile, recomputed every 5 minutes
- **Dynamic 180M profile**: rolling 180-minute profile, recomputed every 15 minutes
- Test window: Mar 11-28 (18 days) in v12/v13

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

## Results (v12) — Extended Test Window + VAH_RECLAIM Overextension Fix (Mar 11–28)

### Strategy Changes from v11
- **Extended test window**: 18 days (Mar 11–28) vs 10 days in v11
- **Fixed VAH_RECLAIM_LONG overextension**: replaced `entry > VAH + ATR` with breakout-specific late-entry filter (`> VAH + 2.5×ATR` AND `> day_open × 1.025` AND 5-bar slope flattening/negative)
- **Fixed target_ok for breakouts**: `min_mult = 1.0` (was 2.0 in v11, blocking targets for wide-stop trades)
- **New `_breakout_slope_flattening()`**: checks 5-bar slope is not steeply rising
- **Apr 1–4 removed**: no Binance data available for those dates

### Results

```
Total: 33 legs (30 distinct entries)
  Wins:  14/33 (42%)
  Total PnL: -1.93% (-1,934 USDT)
  Avg win: 0.37% | Avg loss: -0.37%
  Avg lev: 1.97x | Max lev: 3.00x
  Max single loss: -909 USDT | Max single win: +2,045 USDT

VAH_RECLAIM_LONG:    17 legs, -3,920 USDT (5/17 wins, 29%)
VAL_REJECTION_LONG:   9 legs,  +845 USDT (5/9 wins, 56%)
VAH_REJECTION_SHORT:  7 legs, +1,142 USDT (4/7 wins, 57%)
```

### Candidate Diagnostic Funnel — v12

```
VAH_RECLAIM_LONG (22,609 candidates → 14 entered):
  State OK:     16%  (confirmed above VAH)
  Not extended:  6.5% (overextension fix: 1,473→30, much better than 0.1% in v11)
  Cooldown OK:   0.1% (30 entered cooldown)
  Target OK:     0.06% (14 entered)
  Win rate:      5/17 (29%)

VAL_REJECTION_LONG (22,588 candidates → 9 entered):
  CVD recovery:  8.8% (consistent with v11)
  Not extended:  0.1% (33 passed — tight overextension filter)
  Win rate:      5/9 (56%)

VAH_REJECTION_SHORT (22,595 candidates → 7 entered):
  CVD OK:       40.6% (bearish/failed recovery)
  Not extended:  0.8% (190 passed)
  Win rate:      4/7 (57%)
```

### Key Findings
1. **VAH_RECLAIM_LONG finally triggers** — 14 entries vs 0 in v10/v11, but loses -$3,920. The fundamental issue is timing: most entries (12/17) stop out quickly. The setup works in trending breakouts but fails on intraday whipsaws.
2. **VAL_REJECTION_LONG + VAH_REJECTION_SHORT combined: +$1,987** — these two setups are borderline viable with 56–57% win rates, but volume is too low to overcome VAH_RECLAIM losses.
3. **The main problem is VAH_RECLAIM_LONG itself** — it accounts for 52% of all legs but -$3,920 (-203% of total PnL). The overextension fix allowed entries but the entries are not good quality.
4. **Rolling 24h was dominant** — every single day switched to rolling 24h fallback (gap detection always triggered), so prior-day profiles were never directly used.
5. **42% win rate is below threshold** — strategy needs >50% win rate or larger avg win/avg loss ratio to be profitable.

### What Needs to Change
1. **VAH_RECLAIM_LONG requires a fundamentally different approach** — either stricter entry filters (tighter CVD, stronger delta, volume confirmation) or different target management (wider stops, later entries only after confirmed breakout retest)
2. **Consider disabling VAH_RECLAIM_LONG** and testing the remaining two setups in isolation — they already show +$1,987 with 56–57% win rates
3. **Rolling 24h fallback accuracy** needs investigation — every day was `gap > 0.4%` despite some days having valid prior profiles. The threshold may be too sensitive for volatile crypto markets.

---

## Results (v13) — Composite Context + Dynamic Value Migration (Mar 11–28)

### Design Change
v13 is a fundamental redesign from v12's "level touched + CVD confirmation" model to:
1. **Composite context + value migration** — composite profile (5-day) scored from -3 to +3 for bias; rolling 60M/180M profiles detect value migration
2. **Structure-based stops** — replaces fixed 1× ATR; identifies buyer/seller interest zone
3. **Range rotation targets** — T1=POC (40%), T2=VAH/VAL (40%), runner (20%) if extension eligible
4. **Rejection candle quality** — close_location and body shape checks
5. **3/5 orderflow confirmation** — delta, imbalance, CVD recovery/failure, absorption, volume
6. **VAH_RECLAIM_LONG disabled** — zero actual trading risk, diagnostics only

### Baseline (V13_A) Results

```
Total: 24 legs (24 entries)
  Wins:  11/24 (46%)
  Total PnL: +1.10% (+1,104 USDT)
  Avg win: 0.56% | Avg loss: -0.24%
  Avg lev: 1.46x | Max lev: 3.02x
  Max single loss: -1,208 USDT | Max single win: +1,700 USDT

VAL_REJECTION_LONG:   15 legs, +1,758 USDT (7/15 wins, 47%)
VAH_REJECTION_SHORT:   9 legs,  -654 USDT (4/9 wins, 44%)
```

### Candidate Diagnostic Funnel — Baseline

```
VAL_REJECTION_LONG (25,436 candidates → 12 entered):
  Setup enabled:  46.6%  (1 entry/day cap)
  Composite OK:   40.1%  (6.5% rejected by bearish bias)
  Rejection OK:    0.1%  (10,183 failed — VERY tight rejection candle filter)
  Orderflow OK:    0.1%  (16 passed)
  Stop OK:         0.0%  (12 passed)

VAH_REJECTION_SHORT (25,436 candidates → 8 entered):
  Setup enabled:  71.1%  (looser cap)
  Composite OK:   56.3%  (14.7% rejected by bullish bias)
  Rejection OK:    0.2%  (14,282 failed — rejection candle is main bottleneck)
  Orderflow OK:    0.2%  (45 passed)
  Target OK:       0.0%  (8 passed)
```

### Experiment Comparison

```
Exp   Description              Legs  PnL%     PnL$      Win%  AvgLv
A     Baseline hybrid           24   +1.10%  +1,104     46%  1.46x
B1    Prior-day only            24   +0.56%    +557     46%  1.53x
B2    Rolling 24h only          24   +1.10%  +1,104     46%  1.46x
B3    Hybrid wide stale         24   +1.10%  +1,104     46%  1.46x
C1    POC-only target           20   +0.49%    +491     35%  1.74x
C2    50/50 split target        24   +1.10%  +1,104     46%  1.46x
D1    ATR swing stop            24   +0.85%    +850     46%  1.25x
E1    No bias/migration         24   +1.10%  +1,104     46%  1.46x
E2    Composite bias only       24   +1.10%  +1,104     46%  1.46x
E3    Migration only            24   +1.10%  +1,104     46%  1.46x
E4    Full bias+migration       24   +1.10%  +1,104     46%  1.46x
```

### Key Findings
1. **v13 improves over v12** when VAH_RECLAIM is disabled: +1.10% vs -1.93%. Removing the losing setup was the dominant factor.
2. **VAL_REJECTION_LONG doubled in PnL** — +$1,758 vs +$845 in v12 (15 legs vs 9). The structure stop + range rotation target model increased both entries and PnL.
3. **VAH_REJECTION_SHORT regressed** — -$654 vs +$1,142 in v12. The structure stop may be too tight for shorts, or the range rotation exit doesn't fit short-duration mean-reversion.
4. **Rejection candle filter is the dominant bottleneck** — only 0.1% of candidates pass. This is VERY selective (24 entries from 50,872 candidates across both setups).
5. **Composite bias and migration filters have limited real-world impact** — they reject candidates but rarely affect which entries are ultimately taken. The rejection candle filter dominates.
6. **Profile modes show minimal difference** — prior-day only (B1) underperforms at +0.56%, but all other modes produce identical results. This suggests the stale detection makes little difference in the current market regime.

### What to Improve (v14-v15)
1. ~~**VAH_REJECTION_SHORT needs different treatment**~~ — confirmed flat at $2, moving to diagnostics-only
2. ~~**Rejection candle criteria may be too strict**~~ — 0.55 threshold confirmed near-optimal (E1=$3,324 vs E2/E3=$3,490)
3. ~~**Composite bias should have stronger impact**~~ — confirmed redundant (D1=D5), abandoned
4. ~~**Structure stop validation**~~ — 7 entries is low but max loss $473 is well-controlled

---

## Results (v14) — Fixed Context + 5M Bars (Mar 11–28)

### Infrastructure Fixes
1. **5M bars** — switched from 1M to 5M bars (288 bars/day vs ~1,440)
2. **CandleBuffer bug fixed** — `get_60m_profile()` now computes profiles (was always returning None due to `_60m_cache is None` check before compute)
3. **Migration order fixed** — `update_prev()` called after `migration_state()` (was computing slope against current=previous = 0)
4. **Disk-based download cache** — zip files saved to temp directory, cleared after bar building (~29MB)
5. **DayProfile prev_agg_cache** — stores 3 floats instead of 4M-row DataFrames
6. **1970 chart timestamp fixed** — `entry_ts` now logged in trade records
7. **5-state migration** — STRONG_BULLISH, MODERATE_BULLISH, NEUTRAL_OVERLAP, MODERATE_BEARISH, STRONG_BEARISH
8. **11 CSV exports** — full diagnostic pipeline saved to `outputs/v14/`

### Baseline (V14_A) Results

```
Total: 14 legs (14 entries)
  Wins:  7/14 (50%)
  Total PnL: +3.49% (+3,492 USDT)
  Avg win: 1.40% | Avg loss: -0.25%
  Avg win/avg loss: 2.94
  Avg lev: 0.89x | Max lev: 1.40x
  Max single loss: -473 USDT | Max single win: +1,410 USDT

VAL_REJECTION_LONG:    9 legs, +3,490 USDT (5/9 wins, 56%)
VAH_REJECTION_SHORT:   5 legs,      +2 USDT (2/5 wins, 40%)
```

### Profile Availability + Migration State Distribution

```
60M profile:  3,972/3,972 (100.0%) eligible bars
180M profile: 1,927/1,927 (100.0%) eligible bars

Migration states:
  STRONG_BULLISH:     8 (0.2%)
  MODERATE_BULLISH: 1,264 (26.5%)
  NEUTRAL_OVERLAP:    34 (0.7%)
  NO_CLEAR:        2,544 (53.3%)
  MODERATE_BEARISH:  901 (18.9%)
  STRONG_BEARISH:     18 (0.4%)
```

### Candidate Diagnostic Funnel — Baseline

```
VAL_REJECTION_LONG (4,769 candidates → 7 entered):
  Near level:     100.0%  (all bars considered)
  Setup enabled:   83.1%  (1 entry/day cap)
  Profile valid:   83.1%
  Composite OK:    62.3%  (20.8% rejected by bearish/neutral-bearish)
  Migration OK:    62.3%  (0.1% rejected — minimal impact)
  Rejection OK:     0.6%  (61.7% failed — MAIN bottleneck: close_location, close>=VAL, red candle)
  Orderflow OK:     0.4%  (0.2% failed)
  Stop OK:          0.1%  (0.2% failed — stop_too_wide)
  Target OK:        0.1%  (0 entered failed)

VAH_REJECTION_SHORT (4,769 candidates → 4 entered):
  Near level:     100.0%
  Setup enabled:   85.2%
  Profile valid:   85.2%
  Composite OK:    66.9%  (18.2% rejected)
  Migration OK:    66.9%  (0.1% rejected)
  Rejection OK:     1.3%  (65.6% failed — rejection candle)
  Orderflow OK:     1.2%  (0.1% failed)
  Stop OK:          1.1%  (0.1% failed)
  Target OK:        0.9%  (0.2% failed by target_too_close, 0.8% by size_too_small)
```

### Experiment Comparison

```
Exp   Description                         Legs  PnL%     PnL$      Win%  AvgLv
A     v13 baseline (fixed)                 14   +3.49%  +3,492     50%  0.89x
A0    Fixed migration + 5M bars            14   +3.49%  +3,492     50%  0.89x
A1    VAL_REJECTION only                    9   +3.49%  +3,490     56%  0.98x
B1    VAH_SHORT only strict                14   +3.52%  +3,523     50%  0.89x
C1    VAL + strict VAH                     14   +3.49%  +3,492     50%  0.89x
D1    No composite/migration                9   +3.49%  +3,490     56%  0.98x
D2    Composite only                        9   +3.49%  +3,490     56%  0.98x
D3    Migration only                        9   +3.49%  +3,490     56%  0.98x
D4    Composite + migration                 9   +3.49%  +3,490     56%  0.98x
D5    Strict composite+migration            9   +3.49%  +3,490     56%  0.98x
E1    Close loc >= 0.50                     9   +3.32%  +3,324     56%  0.98x
E2    Close loc >= 0.55                     9   +3.49%  +3,490     56%  0.98x
E3    Close loc >= 0.60                     9   +3.49%  +3,490     56%  0.98x
F1    Entry on next candle                  9   +3.49%  +3,490     56%  0.98x
```

### MFE/MAE by Setup

```
Setup                 Legs  Avg MFE (R)  Avg MAE (R)  Max MFE (R)  Max MAE (R)
VAL_REJECTION_LONG      9       +1.85        -0.33        +4.84        -0.84
VAH_REJECTION_SHORT     5       +1.35        -0.57        +3.04        -1.14
```

Winners average +2.46R MFE and -0.24R MAE; losers average +0.47R MFE and -0.53R MAE. Winning trades run quickly; losing trades never develop favorable movement.

### Context PnL Breakdown

```
Context                              Trades      PnL
NEUTRAL_BULLISH | NO_CLEAR                6  +$4,214  ← all profit driver
NEUTRAL_BULLISH | MODERATE_BEARISH        3    -$724
NEUTRAL_BULLISH | NEUTRAL_OVERLAP         3    +$430
NEUTRAL_BEARISH | NO_CLEAR                 2    -$428
```

No trades occur under BULLISH or BEARISH composite states — only NEUTRAL variants.

### Key Findings

1. **Composite/migration filters are redundant** — D1-D5 produce identical results. Filters block 0 trades that wouldn't already be filtered by rejection candle + orderflow. The 6-factor composite never reaches BULLISH or BEARISH. Recommendation: **abandon** this gating design.

2. **Rejection candle is the sole edge** — 99.4% of candidates filtered here. close_location ≥ 0.55 + close ≥ VAL + red candle checks are the dominant selection mechanism. Very tight but effective.

3. **VAL_REJECTION_LONG is the only viable setup** — +$3,490, 56% win rate, 0.98x avg leverage, max loss $473. VAH_REJECTION_SHORT is flat ($2, 40%) — remove from active trading.

4. **Concentration risk on Mar 28** — 88% of all profit (+$3,082) from a single day. One entry at 69,152 hit POC T1 (+$713) and VAH T2 twice (+$1,360, +$1,410). Without Mar 28: net +$410 over 18 days.

5. **All acceptance criteria met except outlier dependency**: PnL (+$3,492) > $1,104; win rate 50% ≥ 45%; avg win/avg loss 2.94 ≥ 1.25; max loss $473 ≤ $1,000; avg lev 0.89x < 2.0x.

### Outputs

All CSV diagnostics exported to `notebooks/outputs/v14/`:
- `v14_trade_log.csv` — 146 trades across all 15 experiments
- `v14_daily_summary.csv` — per-day PnL breakdown
- `v14_candidate_funnel.csv` — filter pass rates per setup
- `v14_migration_state_distribution.csv` — 5-state counts per experiment
- `v14_vah_reclaim_diagnostic.csv` — 67K breakout/retest observations

---

## Results (v15) — Research-Grade Rewrite (Mar 11–28)

### Design Changes from v14
1. **Auction context model** — replaces v14's six-vote composite score with interpretable geometry (HIGHER_VALUE, LOWER_VALUE, OVERLAPPING_COMPOSITE, DISPLACED_VALUE) and acceptance states
2. **3-category orderflow timing** — aggression, effectiveness, and acceptance are distinct categories (not correlated 3-of-5 votes)
3. **Failed-auction signal** — market probes below VAL within bounded depth, signal bar closes back above VAL, at least one aggression-failure signal + one buyer-response signal
4. **Parquet data pipeline** — aggTrades stored as parquet (was CSV), bookTicker unavailable (returns empty)
5. **Incremental profile caching** — `AuctionContextEngine` maintains rolling merged dicts for 60M/180M profiles instead of rebuilding from scratch each bar
6. **Profile computation fix** — `np.average` moved outside the `max()` lambda, eliminating O(n²) bottleneck (~500s → <1s per daily profile)

### Results (corrected: is_buyer_maker data corruption fixed)

After regenerating the parquet with the correct `is_buyer_maker` (it was all-True due to a
str→bool corruption), the v15 backtest produces **0 positions / 0 trades** over the 18 test
days (Mar 11–28). The earlier "7 positions, −$1,997" was an artifact of that bad data
(fixed in commit `d279687`).

Why 0 trades: the VAL_REJECTION_LONG signal requires all 8 gates True on a single 5-minute
bar (an AND chain). The candidate funnel shows the chain collapses before any bar qualifies:

```
VAL_REJECTION_LONG funnel (5,184 candidate bars over 18 days):
  bounded_probe:        225  (4.3%)   ← strictest first gate
  + reclaim:             70  (1.3%)
  all 8 gates pass:       0  (0.0%)   ← 0 qualifying signals
  near-miss (7/8 gates):  29
```

So there is nothing to trade — the bottleneck is the gate AND-chain, not one bad parameter.
Per review we did NOT immediately loosen thresholds (that overfits). Instead we ran a
**candidate outcome study** (below) to decide where the edge — if any — actually lives.

### Candidate Outcome Study (VAL_REJECTION_LONG)

For every one of the 225 `bounded_probe` candidates we look forward 1 / 3 / 6 / 12 / 24
five-minute bars (5 / 15 / 30 / 60 / 120 min) and measure, in R units (R = per-trade risk):
forward return, MFE, MAE, MFE:MAE ratio, whether price reaches POC before the structural
stop, and POC/stop distances. Candidates are bucketed into 8 progressively-stricter
cumulative-gate groups (G1 = bounded_probe only … G7 = all 7 meaningful gates; G8 = near-miss
passing 7/8 gates). Entry reference = signal-bar close. Source cell: `v15cstudy` in the
executed notebook.

```
Group                     n   h24_mean_fwd(R)   h24_win   h24_MFE   h24_MAE   h24_pct_poc_first   h24_pct_stop_first
G1 bounded_probe        155          -0.016     0.542     6.828     8.377            0.077               0.723
G2 +reclaim              40          -0.376     0.600     2.749     4.037            0.100               0.650
G3 +shape                 9          +0.858     0.778     2.461     2.404            0.333               0.444
G4 +no_lower_acc         16          +0.085     0.562     1.729     2.293            0.062               0.562
G5 +aggression_fail       4          +1.192     0.750     2.181     1.107            0.250               0.250
G6 +buyer_response        1          +1.080     1.000     3.920     0.173            0.000               0.000
G8 near-miss (7/8)       12          +0.194     0.667     2.195     1.999            0.250               0.333
```

Interpretation (answers the 5 review questions):
1. **Is bounded_probe too narrow?** No. G1 has 155 samples but a flat/negative mean return
   (-0.016R, 54% win). The first gate already filters 96% of bars yet its survivors show no
   clear edge — so the probe is not the problem.
2. **Does Shape add edge?** G2→G3 win rate 60%→78%, but G3 has only 9 samples — tentative.
3. **Does Aggression_Failure add incremental value?** G4→G5 h24 return 0.085R→1.192R, but
   G5 has only 4 samples.
4. **Does Buyer_Response over-delay / weaken?** G5→G6 win 75%→100%, but G6 has only 1 sample.
5. **Participation: quality or missed low-volume exhaustion?** Near-miss (7/8) win 67% (n=12);
   fully-qualifying (all 7 gates) = 0 bars.

**Conclusion:** the 0-trade result is caused by the ALL-8-AND gate, not by any single gate.
The stricter groups are far too small (G3–G6 ≤ 16) to read edge reliably. Before changing
thresholds, enlarge the sample (more days / multiple regimes) so the stricter groups have
enough observations. Full per-candidate detail: `v15_candidate_outcome_study.csv`;
group summary: `v15_candidate_outcome_summary.csv`.

### Key Findings
1. **0 trades, corrected data** — prior "7 positions / −$1,997" was an artifact of the
   `is_buyer_maker` str→bool corruption (now fixed: 0 positions).
2. **Gate AND-chain is the bottleneck** — 225 pass the first gate, 70 pass the second, 0 pass
   all 8. The signal model is over-constrained, not under-edged.
3. **bounded_probe survivors are flat** — G1 mean h24 return −0.016R; the probe filter does
   not by itself isolate profitable setups.
4. **Edge (if any) is in the later gates** — G3–G6 show higher win/return, but samples are
   tiny (≤ 16). This is the direction to investigate, not a result to act on yet.
5. **Next step is more data, not looser thresholds** — the study cannot rank gate value on
   18 days; expand the window before tuning.

### Outputs

CSV diagnostics exported to `outputs/v15/`:
- `v15_exit_legs.csv` — per-leg trade records (empty: 0 trades)
- `v15_positions.csv` — closed position summary (empty: 0 trades)
- `v15_candidate_funnel.csv` — filter pass rates per gate (5,184 candidate bars)
- `v15_vah_reclaim_diagnostic.csv` — VAH reclaim breakout/retest observations
- `v15_candidate_outcome_study.csv` — per-candidate forward MFE/MAE / first-touch study (225 rows)
- `v15_candidate_outcome_summary.csv` — 8-group summary of the outcome study

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
- [x] **Fix VAH_RECLAIM_LONG overextension**: Breakout-specific late-entry filter (v12)
- [x] **Extend test window**: 18 days (Mar 11–28) in v12 (Apr 1–4 had no Binance data)
- [x] **VAH_RECLAIM_LONG disabled**: Zero actual trading risk (v13)
- [x] **Composite bias filter**: +3/-3 scoring from composite profile (v13)
- [x] **Dynamic value migration**: 60M/180M rolling profiles (v13)
- [x] **Structure-based stops**: Buyer/seller interest zone instead of fixed ATR (v13)
- [x] **Range rotation targets**: T1 POC 40%, T2 opposite VA 40%, runner 20% (v13)
- [x] **Fix CandleBuffer profile cache**: get_60m_profile never computed profiles (v14)
- [x] **Fix migration slope order**: update_prev was called before migration_state (v14)
- [x] **5M bars**: reduced from 1,440 to 288 bars/day (v14)
- [x] **5-state migration**: STRONG_BULLISH through STRONG_BEARISH (v14)
- [x] **Disk-based download cache**: zip files on disk, cleared after build (v14)
- [x] **11 CSV exports**: full diagnostic pipeline (v14)
- [x] **1970 chart timestamp fixed**: entry_ts now logged (v14)
- [x] **Parquet data pipeline**: aggTrades stored as parquet (v15)
- [x] **Auction context model**: composite geometry, intraday profiles, material migration, acceptance (v15)
- [x] **3-category orderflow**: aggression/effectiveness/acceptance as distinct categories (v15)
- [x] **Failed-auction signal**: bounded probe + reclaim + shape + aggression failure + buyer response (v15)
- [x] **Incremental profile caching**: rolling merged dicts for 60M/180M profiles (v15)
- [x] **Profile computation fix**: np.average moved outside max() lambda, O(n²) → O(n) (v15)
- [x] **Candidate outcome study**: 225 bounded_probe candidates, forward MFE/MAE / first-touch by 8 gate groups (v15, cell `v15cstudy`)
- [ ] **Remove composite/migration filters**: confirmed redundant — D1=D5 identical
- [ ] **VAH_REJECTION_SHORT → diagnostics-only**: flat PnL, 40% win rate
- [ ] **Address concentration risk**: per-day position limits or volatility-based sizing
- [ ] **Rejection candle tuning**: 0.55 threshold is near-optimal but needs robustness testing

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
# Run the v15 notebook (active strategy)
jupyter nbconvert --to notebook --execute notebooks/profile_orderflow_strategy_v15.ipynb --output notebooks/profile_orderflow_strategy_v15_executed.ipynb --ExecutePreprocessor.timeout=-1

# Or via CLI with nbconvert + python
jupyter nbconvert --to script notebooks/profile_orderflow_strategy_v15.ipynb --output v15_run
python notebooks/v15_run.py

# Run the v14 reference (15-experiment matrix)
jupyter nbconvert --to notebook --execute notebooks/profile_orderflow_strategy_v14.ipynb --output notebooks/profile_orderflow_strategy_v14_executed.ipynb --ExecutePreprocessor.timeout=-1
```

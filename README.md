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
| `profile_orderflow_strategy.ipynb` | **Main strategy** — v9: Value boundary entries, CVD regime filter, multi-target exits |
| `profile_orderflow_strategy_executed.ipynb` | Same as above with all outputs pre-executed |
| `btcusdt_orderflow_backtest.ipynb` | First orderflow prototype (OrderBookImbalance-based, reference only) |
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

### Entry Logic (v8/v9)
```
Mean-reversion (VAL rejection L / VAH rejection S):
  Entry at prior VAL/VAH + CVD regime + local divergence + delta + imbalance
  Target: prior POC

Breakout (VAH reclaim L / VAL breakdown S):
  3-bar confirmation above VAH / below VAL + CVD regime + delta + imbalance
  Multi-target: +1R (50%), +2R (30%), runner trail
```

### Dynamic Position Sizing
```
Position (BTC) = Account × 2% ÷ StopDistance
StopDistance = Entry − StopLevel
```
- Stop: min(absorption bar low × 0.997, entry × 0.98) for longs
- Stop: max(exhaustion bar high × 1.003, entry × 1.02) for shorts
- Breakeven after 0.5% move in favor

### Profile Sources
- **Composite**: 5 trading days (Mar 4-8) — for market context only
- **Prior day**: single-day VAL/VAH/POC — for entry trigger levels
- Test window: Mar 11-15 (5 consecutive days)

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

## Future Plans

### Short-term Fixes (next iteration)
- [x] **Re-entry cooldown**: Block re-entries for N bars after a stopped-out trade (v8)
- [x] **ATR-based stops**: ATR-based stop buffers on breakout trades (v8, 0.5× ATR buffer at VAL/VAH acceptance level)
- [x] **Trailing stop**: Runner trail at 0.5× R / 0.5× ATR on breakout trades (v8)
- [x] **Additional data window**: Extended to 10 trading days (Mar 11-22) in v9
- [ ] **Max position size cap**: Limit notional leverage to prevent 10+ BTC positions
- [ ] **VAL breakdown removal or fix**: This entry type is a consistent loser
- [ ] **Weekend gap handling**: Adjust prior-day profile relevance after weekends
- [ ] **Stronger divergence filter**: Require bar close near extreme or minimum CVD gap

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
# Build and run the v7 notebook
python scripts/build_v7.py
jupyter nbconvert --to notebook --execute notebooks/profile_orderflow_strategy.ipynb

# Or open interactively
jupyter notebook notebooks/profile_orderflow_strategy.ipynb
```

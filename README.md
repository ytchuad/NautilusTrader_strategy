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
| `profile_orderflow_strategy.ipynb` | **Main strategy** — v7: POC-based entries, CVD divergence, dynamic sizing |
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

### v7 — POC Reversal/Continuation (current)
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

### Entry Logic (v7)
```
Price near prior day POC (within 0.2%):
  ├─ CVD absorption + buy delta (>2%) + bid imbalance (>1.2×) → LONG
  └─ CVD exhaustion + sell delta (<−2%) + ask imbalance (>1.2×) → SHORT
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
- [ ] **Re-entry cooldown**: Block re-entries for N bars after a stopped-out trade
- [ ] **ATR-based stops**: Wider stops (1.5× ATR) instead of fixed 2% to reduce whipsaw
- [ ] **Stronger divergence filter**: Require bar close near extreme or minimum CVD gap

### Mid-term Improvements
- [ ] **Trailing stop**: Trail after breakeven instead of hard VAL/VAH targets
- [ ] **Additional data window**: Extend beyond Mar 11-15 to cover more market regimes
- [ ] **Multi-timeframe profile**: Use intraday profiles (e.g., Asian/London/NY sessions) alongside daily
- [ ] **Machine learning filter**: Classify high-probability vs. low-probability divergence signals

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

## Reproducing the Backtest

```bash
# Build and run the v7 notebook
python scripts/build_v7.py
jupyter nbconvert --to notebook --execute notebooks/profile_orderflow_strategy.ipynb

# Or open interactively
jupyter notebook notebooks/profile_orderflow_strategy.ipynb
```

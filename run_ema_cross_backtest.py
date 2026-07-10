"""
First NautilusTrader Backtest
==============================
Runs the official EMA cross + TWAP example using bundled ETHUSDT trade tick data.
"""

import time
from decimal import Decimal

import pandas as pd

from nautilus_trader.adapters.binance import BINANCE_VENUE
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig
from nautilus_trader.examples.algorithms.twap import TWAPExecAlgorithm
from nautilus_trader.examples.strategies.ema_cross_twap import EMACrossTWAP
from nautilus_trader.examples.strategies.ema_cross_twap import EMACrossTWAPConfig
from nautilus_trader.model.currencies import ETH
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import BookType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.wranglers import TradeTickDataWrangler
from nautilus_trader.test_kit.providers import TestDataProvider
from nautilus_trader.test_kit.providers import TestInstrumentProvider

if __name__ == "__main__":
    print("=" * 60)
    print("  NautilusTrader EMA Cross Backtest")
    print("=" * 60)

    config = BacktestEngineConfig(
        trader_id=TraderId("BACKTESTER-001"),
        logging=LoggingConfig(log_level="WARN", use_pyo3=False),
    )

    engine = BacktestEngine(config=config)

    engine.add_venue(
        venue=BINANCE_VENUE,
        oms_type=OmsType.NETTING,
        book_type=BookType.L1_MBP,
        account_type=AccountType.CASH,
        base_currency=None,
        starting_balances=[Money(1_000_000.0, USDT), Money(10.0, ETH)],
    )

    ETHUSDT_BINANCE = TestInstrumentProvider.ethusdt_binance()
    engine.add_instrument(ETHUSDT_BINANCE)

    print("\nLoading test data...")
    provider = TestDataProvider()
    wrangler = TradeTickDataWrangler(instrument=ETHUSDT_BINANCE)
    ticks = wrangler.process(provider.read_csv_ticks("binance/ethusdt-trades.csv"))
    engine.add_data(ticks)
    print(f"  Loaded {len(ticks)} trade ticks")

    strategy_config = EMACrossTWAPConfig(
        instrument_id=ETHUSDT_BINANCE.id,
        bar_type=BarType.from_str("ETHUSDT.BINANCE-250-TICK-LAST-INTERNAL"),
        trade_size=Decimal("0.10"),
        fast_ema_period=10,
        slow_ema_period=20,
        twap_horizon_secs=10.0,
        twap_interval_secs=2.5,
    )

    strategy = EMACrossTWAP(config=strategy_config)
    engine.add_strategy(strategy=strategy)

    exec_algorithm = TWAPExecAlgorithm()
    engine.add_exec_algorithm(exec_algorithm)

    print("\nRunning backtest...")
    engine.run()

    print("\n" + "=" * 60)
    print("  Results Summary")
    print("=" * 60)

    account_report = engine.trader.generate_account_report(BINANCE_VENUE)
    positions_report = engine.trader.generate_positions_report()

    # Extract starting/ending USDT balance
    usdt_entries = account_report[account_report["currency"] == "USDT"]
    usdt_start = float(usdt_entries.iloc[0]["total"])
    usdt_end = float(usdt_entries.iloc[-1]["total"])

    # Sum realized PnL from positions
    positions_report = positions_report.reset_index()
    # realized_pnl is a Money column - extract float from first element
    def money_to_float(val):
        if hasattr(val, "as_double"):
            return float(val.as_double())
        return float(str(val).split()[0])

    total_pnl = sum(money_to_float(v) for v in positions_report["realized_pnl"])
    num_trades = len(positions_report)
    wins = sum(1 for v in positions_report["realized_pnl"] if money_to_float(v) > 0)

    print(f"""
  Trading Period : {usdt_entries.index[0].strftime('%Y-%m-%d %H:%M UTC')}  ->  {usdt_entries.index[-1].strftime('%Y-%m-%d %H:%M UTC')}
  Starting Capital: {usdt_start:,.2f} USDT
  Ending Capital  : {usdt_end:,.2f} USDT
  Net PnL         : {total_pnl:+.2f} USDT
  Number of Trades: {num_trades}
  Win Rate        : {wins}/{num_trades}
""")

    engine.dispose()
    print("Done!")

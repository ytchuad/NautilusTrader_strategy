"""
Binance Public Data Explorer
=============================
Query available data types, symbols, and date ranges
from the Binance public data S3 bucket.

Usage:
    python scripts/explore_binance_data.py                  # List data types
    python scripts/explore_binance_data.py -d trades        # List symbols
    python scripts/explore_binance_data.py -d trades -s BTCUSDT  # Date range
    python scripts/explore_binance_data.py -m spot          # Spot market
"""

import argparse
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, quote

import urllib.request
import urllib.error


S3_BUCKET = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"

MARKET_PREFIXES = {
    "spot": "data/spot",
    "um": "data/futures/um",
    "cm": "data/futures/cm",
}

MARKET_NAMES = {
    "spot": "Spot",
    "um": "USD-M Futures",
    "cm": "COIN-M Futures",
}


def list_prefix_paginated(prefix: str, delimiter: str | None = None) -> list[dict]:
    """List objects under prefix with pagination. Each entry has
    key, size (int), last_modified (str), and is_dir (bool)."""
    all_entries = []
    marker = None

    while True:
        params = {"prefix": prefix}
        if delimiter:
            params["delimiter"] = delimiter
        if marker:
            params["marker"] = marker

        url = f"{S3_BUCKET}?{urlencode(params)}"
        try:
            resp = urllib.request.urlopen(url, timeout=30)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return all_entries
            print(f"HTTP Error {e.code}: {prefix}")
            return all_entries
        except urllib.error.URLError as e:
            print(f"URL Error: {e}")
            return all_entries

        root = ET.fromstring(resp.read().decode())

        # Directories (CommonPrefixes)
        for cp in root.iter(f"{NS}CommonPrefixes"):
            pfx = cp.find(f"{NS}Prefix")
            if pfx is not None and pfx.text:
                all_entries.append({
                    "key": pfx.text,
                    "size": 0,
                    "last_modified": "",
                    "is_dir": True,
                })

        # Files (Contents)
        for c in root.iter(f"{NS}Contents"):
            key_elem = c.find(f"{NS}Key")
            if key_elem is None or not key_elem.text:
                continue
            size_elem = c.find(f"{NS}Size")
            lm_elem = c.find(f"{NS}LastModified")
            all_entries.append({
                "key": key_elem.text,
                "size": int(size_elem.text) if size_elem is not None and size_elem.text else 0,
                "last_modified": lm_elem.text if lm_elem is not None and lm_elem.text else "",
                "is_dir": False,
            })

        # Pagination
        is_truncated = root.find(f"{NS}IsTruncated")
        if is_truncated is None or is_truncated.text != "true":
            break
        next_marker = root.find(f"{NS}NextMarker")
        if next_marker is not None and next_marker.text:
            marker = next_marker.text
        elif all_entries and not all_entries[-1]["is_dir"]:
            marker = all_entries[-1]["key"]
        else:
            break

    return all_entries


def show_data_types(market: str):
    print(f"\nAvailable Data Types: {MARKET_NAMES[market]} ({market})\n")
    for freq in ["daily", "monthly"]:
        prefix = f"{MARKET_PREFIXES[market]}/{freq}/"
        entries = list_prefix_paginated(prefix, delimiter="/")
        types = sorted(e["key"].replace(prefix, "").rstrip("/")
                       for e in entries if e["is_dir"])
        print(f"  [{freq.upper()}]")
        for t in types:
            print(f"    - {t}")
        print()


def show_symbols(market: str, data_type: str, freq: str = "daily"):
    prefix = f"{MARKET_PREFIXES[market]}/{freq}/{data_type}/"
    entries = list_prefix_paginated(prefix, delimiter="/")
    symbols = sorted(e["key"].replace(prefix, "").rstrip("/")
                     for e in entries if e["is_dir"])

    if not symbols:
        print(f"  (no symbols found for {data_type}/{freq})")
        return

    print(f"\nSymbols ({freq}/{data_type}): {len(symbols)} total\n")
    for sym in symbols:
        print(f"  {sym}")


def show_date_range(market: str, data_type: str, symbol: str, freq: str = "daily"):
    if freq == "daily":
        if data_type == "klines":
            # klines has interval subdirs
            intervals = ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "6h",
                         "8h", "12h", "1d", "3d", "1w", "1mo"]
            print(f"\nDate range: {symbol} / {data_type} / {freq}")
            for interval in intervals:
                prefix = f"{MARKET_PREFIXES[market]}/{freq}/{data_type}/{symbol}/{interval}/{symbol}-{interval}-"
                entries = list_prefix_paginated(prefix)
                zips = sorted(set(
                    e["key"].rsplit("/", 1)[1] for e in entries
                    if not e["is_dir"] and e["key"].endswith(".zip")
                ))
                if zips:
                    print(f"  {interval:>4}: {zips[0].rsplit('.',1)[0]} ~ {zips[-1].rsplit('.',1)[0]} ({len(zips)} files)")
            return

        # Regular daily files
        prefix = f"{MARKET_PREFIXES[market]}/{freq}/{data_type}/{symbol}/{symbol}-{data_type}-"
        entries = list_prefix_paginated(prefix)
        zips = sorted(set(
            e["key"].rsplit("/", 1)[1] for e in entries
            if not e["is_dir"] and e["key"].endswith(".zip")
        ))
    else:
        # Monthly
        prefix = f"{MARKET_PREFIXES[market]}/{freq}/{data_type}/{symbol}/{symbol}-{data_type}-"
        entries = list_prefix_paginated(prefix)
        zips = sorted(set(
            e["key"].rsplit("/", 1)[1] for e in entries
            if not e["is_dir"] and e["key"].endswith(".zip")
        ))

    if not zips:
        print(f"  (no data for {symbol} / {data_type} / {freq})")
        return

    first = zips[0].rsplit(".", 1)[0].replace(f"{symbol}-{data_type}-", "")
    last = zips[-1].rsplit(".", 1)[0].replace(f"{symbol}-{data_type}-", "")
    print(f"\n{symbol} / {data_type} / {freq}")
    print(f"  Range: {first} ~ {last}")
    print(f"  Files: {len(zips)}")

    # Gap analysis for daily dates
    if freq == "daily" and "-" in first:
        dates = sorted(set(
            z.rsplit(".", 1)[0].replace(f"{symbol}-{data_type}-", "")
            for z in zips
        ))
        missing = []
        for i in range(len(dates) - 1):
            try:
                d1 = datetime.strptime(dates[i], "%Y-%m-%d")
                d2 = datetime.strptime(dates[i + 1], "%Y-%m-%d")
                expected = d1 + timedelta(days=1)
                if d2 > expected:
                    missing.append((d1 + timedelta(days=1), d2 - timedelta(days=1)))
            except ValueError:
                pass
        if missing:
            print(f"  Gaps: {len(missing)}")
            for s, e in missing[:5]:
                print(f"    {s.date()} ~ {e.date()}")
        else:
            print(f"  Gaps: none")
    print()


def main():
    parser = argparse.ArgumentParser(description="Binance Public Data Explorer")
    parser.add_argument("-m", "--market", choices=list(MARKET_PREFIXES.keys()),
                        default="um", help="Market type (default: um)")
    parser.add_argument("-d", "--data-type", default=None,
                        help="Data type: trades, aggTrades, klines, bookDepth, ...")
    parser.add_argument("-s", "--symbol", default=None,
                        help="Symbol e.g. BTCUSDT")
    parser.add_argument("-f", "--freq", choices=["daily", "monthly"], default=None,
                        help="Frequency (default: both)")

    args = parser.parse_args()

    print("=" * 60)
    print(f"  Binance Public Data Explorer")
    print(f"  Market: {MARKET_NAMES[args.market]} ({args.market})")
    print(f"  Time:   {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    if args.data_type is None:
        show_data_types(args.market)
    elif args.symbol is None:
        freqs = [args.freq] if args.freq else ["daily", "monthly"]
        for freq in freqs:
            show_symbols(args.market, args.data_type, freq)
    else:
        freqs = [args.freq] if args.freq else ["daily", "monthly"]
        for freq in freqs:
            show_date_range(args.market, args.data_type, args.symbol, freq)


if __name__ == "__main__":
    main()

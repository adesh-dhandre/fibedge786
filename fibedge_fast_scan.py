import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fibedge_shared_cache import (
    completed_daily,
    now_ist,
    refresh_market_cache,
)

from archive.premium_v1.premium_plus_scanner import find_candidate as premium_plus_find
from strategy_05_live.strategy_05_scanner import find_latest_signal as strategy05_find

UNIVERSE_FILE = "NSE_STOCK_UNIVERSE.csv"

CLASSIC_OUTPUT = "ALL_NSE_CURRENT_SETUPS_V3.csv"
LATEST_OUTPUT = "FIBEDGE_LATEST_SIGNALS.csv"
FAILED_OUTPUT = "ALL_NSE_FAILED_SYMBOLS_V3.csv"

PREMIUM_PLUS_OUTPUT = Path("archive/premium_v1/data/premium_plus_candidates.json")
PREMIUM_PLUS_FAILED = Path("archive/premium_v1/data/premium_plus_failed_symbols.csv")

STRATEGY05_OUTPUT = Path("strategy_05_live/data/strategy_05_candidates.json")
STRATEGY05_FAILED = Path("strategy_05_live/data/strategy_05_failed_symbols.csv")

MIN_DECLINE = 0.08
MIN_SWING_DAYS = 15
FIB_ENTRY = 0.786
FIB_SL = 0.500
FIB_TARGET = 1.260
NEAR_ENTRY_PCT = 2.0


def classic_find_setup(df):
    if df is None or len(df) < 40:
        return None

    df = df.copy().reset_index(drop=True)

    high_price = float(df.loc[0, "High"])
    high_date = pd.Timestamp(df.loc[0, "Date"])
    state = "SEARCH_HIGH"

    low_price = None
    low_date = None
    low_idx = None
    entry = None
    sl = None
    target = None
    entry_date = None

    for i in range(1, len(df)):
        date = pd.Timestamp(df.loc[i, "Date"])
        candle_high = float(df.loc[i, "High"])
        candle_low = float(df.loc[i, "Low"])

        if state == "SEARCH_HIGH":
            if candle_high > high_price:
                high_price = candle_high
                high_date = date

            decline = (high_price - candle_low) / high_price
            days = (date - high_date).days

            if decline >= MIN_DECLINE and days >= MIN_SWING_DAYS:
                state = "TRACK_LOW"
                low_price = candle_low
                low_date = date
                low_idx = i

        elif state == "TRACK_LOW":
            if candle_low < low_price:
                low_price = candle_low
                low_date = date
                low_idx = i

            price_range = high_price - low_price
            sl = low_price + price_range * FIB_SL
            entry = low_price + price_range * FIB_ENTRY
            target = low_price + price_range * FIB_TARGET

            if i <= low_idx:
                continue

            if candle_high >= entry:
                entry_date = date

                if candle_low <= sl or candle_high >= target:
                    state = "SEARCH_HIGH"
                    high_price = candle_high
                    high_date = date
                    low_price = None
                    low_date = None
                    low_idx = None
                    entry = None
                    sl = None
                    target = None
                    entry_date = None
                else:
                    state = "OPEN"

        elif state == "OPEN":
            if candle_low <= sl or candle_high >= target:
                state = "SEARCH_HIGH"
                high_price = candle_high
                high_date = date
                low_price = None
                low_date = None
                low_idx = None
                entry = None
                sl = None
                target = None
                entry_date = None

    if state == "TRACK_LOW":
        price_range = high_price - low_price
        return {
            "Structure": "TRACKING",
            "High Date": high_date.date(),
            "High": high_price,
            "Low Date": pd.Timestamp(low_date).date(),
            "Low": low_price,
            "Entry Date": None,
            "Entry": low_price + price_range * FIB_ENTRY,
            "SL": low_price + price_range * FIB_SL,
            "Target": low_price + price_range * FIB_TARGET,
        }

    if state == "OPEN":
        return {
            "Structure": "OPEN",
            "High Date": high_date.date(),
            "High": high_price,
            "Low Date": pd.Timestamp(low_date).date(),
            "Low": low_price,
            "Entry Date": pd.Timestamp(entry_date).date() if entry_date is not None else None,
            "Entry": entry,
            "SL": sl,
            "Target": target,
        }

    return None


def classic_classify(setup, price):
    if setup is None:
        return "NO CURRENT SETUP", None

    entry = setup["Entry"]
    sl = setup["SL"]
    target = setup["Target"]

    if setup["Structure"] == "OPEN":
        distance = (price - entry) / entry * 100.0

        if price <= sl:
            return "SL HIT", distance
        if price >= target:
            return "TARGET HIT", distance
        return "OPEN", distance

    distance = (entry - price) / entry * 100.0

    if price >= entry:
        return "ENTRY AREA", distance
    if distance <= NEAR_ENTRY_PCT:
        return "NEAR 0.786", distance
    return "WAITING FOR 0.786", distance


def build_classic(market, symbols):
    started = time.time()
    rows = []
    failed = []
    scan_time = now_ist().isoformat()

    for symbol in symbols:
        raw = market.get(symbol)
        if raw is None or raw.empty:
            failed.append(symbol)
            continue

        structure_df = completed_daily(raw)
        if structure_df is None or len(structure_df) < 40:
            failed.append(symbol)
            continue

        try:
            setup = classic_find_setup(structure_df)
            latest_price = float(raw["Close"].iloc[-1])
            status, distance = classic_classify(setup, latest_price)

            rows.append({
                "Symbol": symbol,
                "Price": latest_price,
                "Price Time": scan_time,
                "Status": status,
                "High Date": setup["High Date"] if setup else None,
                "High": setup["High"] if setup else None,
                "Low Date": setup["Low Date"] if setup else None,
                "Low": setup["Low"] if setup else None,
                "Entry Date": setup["Entry Date"] if setup else None,
                "Entry": setup["Entry"] if setup else None,
                "SL": setup["SL"] if setup else None,
                "Target": setup["Target"] if setup else None,
                "Distance %": distance,
            })
        except Exception:
            failed.append(symbol)

    df = pd.DataFrame(rows)

    if not df.empty:
        priority = {
            "TARGET HIT": 1,
            "SL HIT": 2,
            "OPEN": 3,
            "NEAR 0.786": 4,
            "ENTRY AREA": 5,
            "WAITING FOR 0.786": 6,
            "NO CURRENT SETUP": 7,
        }
        df["_Priority"] = df["Status"].map(priority).fillna(9)
        df = df.sort_values(
            ["_Priority", "Distance %"],
            na_position="last",
        ).drop(columns=["_Priority"])

    df.to_csv(CLASSIC_OUTPUT, index=False)
    df.to_csv(LATEST_OUTPUT, index=False)
    pd.DataFrame({"Symbol": failed}).to_csv(FAILED_OUTPUT, index=False)

    print("Classic current structures:", len(df), "| failed:", len(failed))
    print("Classic calculation:", round(time.time() - started, 2), "sec")

    # Existing ranking logic remains unchanged.
    subprocess.check_call([sys.executable, "fibedge_quality_live_merge.py"])
    subprocess.check_call([sys.executable, "fibedge_opportunity_rank_v3.py"])

    return {
        "rows": len(df),
        "failed": len(failed),
        "duration_seconds": time.time() - started,
    }


def build_premium_plus(market, symbols):
    started = time.time()
    candidates = []
    failed = []
    latest_market_date = None

    for symbol in symbols:
        raw = market.get(symbol)
        df = completed_daily(raw)

        if df is None or len(df) < 40:
            failed.append(symbol)
            continue

        d = pd.Timestamp(df["Date"].iloc[-1]).date()
        if latest_market_date is None or d > latest_market_date:
            latest_market_date = d

        try:
            result = premium_plus_find(symbol, df)
            if result is not None:
                candidates.append(result)
        except Exception:
            failed.append(symbol)

    candidates.sort(
        key=lambda r: (
            -float(r.get("close_vs_786_pct", 0)),
            r.get("symbol", ""),
        )
    )

    finished = now_ist()
    payload = {
        "strategy": "FibEdge Premium+ V1",
        "updated_at": finished.isoformat(),
        "scan_finished_at_ist": finished.isoformat(),
        "market_date": latest_market_date.isoformat() if latest_market_date else None,
        "candidate_count": len(candidates),
        "frozen_rules": {
            "base_min_decline_pct": 8,
            "premium_min_decline_pct": 15,
            "min_swing_days": 15,
            "max_lower_wick_pct": 10,
            "max_compression_3v10": 0.90,
            "min_close_above_786_pct": 2.0,
            "signal_timing": "after completed daily candle",
            "entry_timing": "next session",
        },
        "candidates": candidates,
    }

    PREMIUM_PLUS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PREMIUM_PLUS_OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame({"Symbol": failed}).to_csv(PREMIUM_PLUS_FAILED, index=False)

    print("Premium+ candidates:", len(candidates), "| failed:", len(failed))
    print("Premium+ calculation:", round(time.time() - started, 2), "sec")

    return {
        "candidates": len(candidates),
        "failed": len(failed),
        "duration_seconds": time.time() - started,
    }


def build_strategy05(market, symbols):
    started = time.time()
    candidates = []
    failed = []
    latest_market_date = None

    for symbol in symbols:
        raw = market.get(symbol)
        df = completed_daily(raw)

        if df is None or len(df) < 40:
            failed.append(symbol)
            continue

        d = pd.Timestamp(df["Date"].iloc[-1]).date()
        if latest_market_date is None or d > latest_market_date:
            latest_market_date = d

        try:
            result = strategy05_find(symbol, df)
            if result is not None:
                candidates.append(result)
        except Exception:
            failed.append(symbol)

    candidates.sort(
        key=lambda r: (
            -float(r.get("close_vs_786_pct", 0)),
            -float(r.get("body_pct_range", 0)),
            r.get("symbol", ""),
        )
    )

    finished = now_ist()
    payload = {
        "strategy": "FibEdge Confirmed Continuation",
        "updated_at": finished.isoformat(),
        "scan_finished_at_ist": finished.isoformat(),
        "market_date": latest_market_date.isoformat() if latest_market_date else None,
        "candidate_count": len(candidates),
        "cache_window": "1y",
        "frozen_rule": {
            "fib_entry": 0.786,
            "fib_stop": 0.500,
            "primary_target": 1.260,
            "extension_target": 1.500,
            "min_close_above_786_pct": 4.0,
            "min_body_pct_range": 60.0,
            "signal_timing": "after completed daily candle",
            "entry_timing": "next session",
        },
        "historical_research": {
            "primary_1260": {
                "resolved_trades": 1060,
                "win_rate_pct": 87.924528,
                "unique_stocks": 707,
            },
            "extension_1500": {
                "resolved_trades": 1023,
                "win_rate_pct": 77.126100,
                "unique_stocks": 691,
            },
        },
        "candidates": candidates,
    }

    STRATEGY05_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    STRATEGY05_OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame({"Symbol": failed}).to_csv(STRATEGY05_FAILED, index=False)

    print("Strategy 05 candidates:", len(candidates), "| failed:", len(failed))
    print("Strategy 05 calculation:", round(time.time() - started, 2), "sec")

    return {
        "candidates": len(candidates),
        "failed": len(failed),
        "duration_seconds": time.time() - started,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "strategy",
        nargs="?",
        default="ALL",
        choices=["ALL", "CLASSIC", "CLEAN", "PREMIUM", "PREMIUMPLUS", "STRATEGY05"],
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force a new 1-year cache seed instead of the normal 5-day incremental refresh.",
    )
    args = parser.parse_args()

    started = time.time()
    universe = pd.read_csv(UNIVERSE_FILE)
    symbols = (
        universe["YF_SYMBOL"]
        .dropna()
        .astype(str)
        .str.strip()
        .drop_duplicates()
        .tolist()
    )

    print("=" * 92)
    print("FIBEDGE FAST WEBSITE SCAN")
    print("=" * 92)
    print("Strategy:", args.strategy)
    print("Structure window: 1 year")
    print("Cache refresh: 5 trading days after initial seed")
    print()

    market, cache_stats = refresh_market_cache(
        symbols,
        force_full=args.full,
    )

    results = {}

    if args.strategy in ("ALL", "CLASSIC", "CLEAN", "PREMIUM"):
        results["classic_source"] = build_classic(market, symbols)

    if args.strategy in ("ALL", "PREMIUMPLUS"):
        results["premium_plus"] = build_premium_plus(market, symbols)

    if args.strategy in ("ALL", "STRATEGY05"):
        results["strategy05"] = build_strategy05(market, symbols)

    total = time.time() - started

    summary = {
        "strategy": args.strategy,
        "finished_at_ist": now_ist().isoformat(),
        "structure_window": "1y",
        "cache": cache_stats,
        "results": results,
        "total_duration_seconds": total,
        "target_seconds": 180,
        "under_3_minutes": total < 180,
    }

    Path(".fibedge_cache").mkdir(parents=True, exist_ok=True)
    Path(".fibedge_cache/last_fast_scan.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print()
    print("=" * 92)
    print("FAST SCAN SUMMARY")
    print("=" * 92)
    print("Total:", round(total, 2), "sec")
    print("Under 3 minutes:", "YES" if total < 180 else "NO")
    print("Cache backend:", cache_stats.get("backend"))
    print("=" * 92)


if __name__ == "__main__":
    main()

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from fibedge_shared_cache import (
    completed_daily,
    get_cache,
    now_ist,
    refresh_market_cache,
)

UNIVERSE_FILE = "NSE_STOCK_UNIVERSE.csv"

CLASSIC_OUTPUT = Path("ALL_NSE_CURRENT_SETUPS_V3.csv")
LATEST_OUTPUT = Path("FIBEDGE_LATEST_SIGNALS.csv")
FAILED_OUTPUT = Path("ALL_NSE_FAILED_SYMBOLS_V3.csv")

PREMIUM_PLUS_OUTPUT = Path("archive/premium_v1/data/premium_plus_candidates.json")
PREMIUM_PLUS_FAILED = Path("archive/premium_v1/data/premium_plus_failed_symbols.csv")

STRATEGY05_OUTPUT = Path("strategy_05_live/data/strategy_05_candidates.json")
STRATEGY05_FAILED = Path("strategy_05_live/data/strategy_05_failed_symbols.csv")

MIN_DECLINE = 0.08
MIN_SWING_DAYS = 15

FIB_ENTRY = 0.786
FIB_SL = 0.500
FIB_TARGET_126 = 1.260
FIB_TARGET_150 = 1.500

NEAR_ENTRY_PCT = 2.0

PREMIUM_MIN_DECLINE_PCT = 15.0
PREMIUM_MAX_LOWER_WICK_PCT = 10.0
PREMIUM_MAX_COMPRESSION_3V10 = 0.90
PREMIUM_MIN_CLOSE_ABOVE_786_PCT = 2.0

S05_MIN_CLOSE_ABOVE_786_PCT = 4.0
S05_MIN_BODY_PCT_RANGE = 60.0


def _date_days(a, b):
    return int((a - b) / np.timedelta64(1, "D"))


def _rsi14_last(closes):
    if len(closes) < 15:
        return None

    delta = np.diff(closes[-15:])
    gain = np.maximum(delta, 0.0)
    loss = np.maximum(-delta, 0.0)

    avg_gain = float(np.mean(gain))
    avg_loss = float(np.mean(loss))

    # Matches the existing implementation, which turns zero avg_loss into NaN.
    if avg_loss == 0:
        return None

    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))


def _last_atr_ratio(highs, lows, closes):
    n = len(closes)
    if n < 10:
        return None

    start = n - 10
    tr = []

    for i in range(start, n):
        base = highs[i] - lows[i]

        if i == 0:
            value = base
        else:
            prev = closes[i - 1]
            value = max(
                base,
                abs(highs[i] - prev),
                abs(lows[i] - prev),
            )

        tr.append(float(value))

    atr10 = float(np.mean(tr))
    atr3 = float(np.mean(tr[-3:]))

    if atr10 == 0:
        return None

    return atr3 / atr10


def analyze_stock_fast(symbol, df):
    """
    One state-machine pass produces the shared Fibonacci structure plus both
    confirmation candidates. This preserves the frozen rules while avoiding
    three separate one-year replays per stock.
    """
    if df is None or len(df) < 40:
        return None, None, None

    dates = df["Date"].to_numpy(dtype="datetime64[ns]")
    opens = df["Open"].to_numpy(dtype=float)
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)

    n = len(df)
    last_idx = n - 1

    # 0=SEARCH_HIGH, 1=TRACK_LOW, 2=OPEN
    state = 0

    high_price = float(highs[0])
    high_date = dates[0]

    low_price = None
    low_date = None
    low_idx = None

    entry = None
    sl = None
    target_126 = None
    entry_date = None

    premium_candidate = None
    strategy05_candidate = None

    for i in range(1, n):
        date = dates[i]
        candle_high = float(highs[i])
        candle_low = float(lows[i])

        if state == 0:
            if candle_high > high_price:
                high_price = candle_high
                high_date = date

            decline = (high_price - candle_low) / high_price
            days = _date_days(date, high_date)

            if decline >= MIN_DECLINE and days >= MIN_SWING_DAYS:
                state = 1
                low_price = candle_low
                low_date = date
                low_idx = i

        elif state == 1:
            if candle_low < low_price:
                low_price = candle_low
                low_date = date
                low_idx = i

            price_range = high_price - low_price
            sl = low_price + price_range * FIB_SL
            entry = low_price + price_range * FIB_ENTRY
            target_126 = low_price + price_range * FIB_TARGET_126

            if i <= low_idx:
                continue

            if candle_high >= entry:
                entry_date = date

                # The confirmation strategies only produce a live candidate
                # when the latest completed candle is the 0.786 touch candle.
                if i == last_idx:
                    candle_open = float(opens[i])
                    candle_close = float(closes[i])
                    candle_range = candle_high - candle_low

                    if candle_range > 0:
                        close_above = (candle_close / entry - 1.0) * 100.0
                        body_pct = (
                            abs(candle_close - candle_open)
                            / candle_range
                            * 100.0
                        )
                        decline_pct = (
                            (high_price - low_price)
                            / high_price
                            * 100.0
                        )
                        swing_days = _date_days(low_date, high_date)
                        recovery_days = _date_days(date, low_date)
                        target_150 = (
                            low_price
                            + price_range * FIB_TARGET_150
                        )

                        lower_wick = min(candle_open, candle_close) - candle_low
                        lower_wick_pct = (
                            max(lower_wick, 0.0)
                            / candle_range
                            * 100.0
                        )
                        compression = _last_atr_ratio(
                            highs,
                            lows,
                            closes,
                        )

                        if (
                            decline_pct >= PREMIUM_MIN_DECLINE_PCT
                            and swing_days >= MIN_SWING_DAYS
                            and lower_wick_pct <= PREMIUM_MAX_LOWER_WICK_PCT
                            and compression is not None
                            and np.isfinite(compression)
                            and compression <= PREMIUM_MAX_COMPRESSION_3V10
                            and close_above >= PREMIUM_MIN_CLOSE_ABOVE_786_PCT
                        ):
                            premium_candidate = {
                                "symbol": symbol,
                                "signal_date": pd.Timestamp(date).date().isoformat(),
                                "close": candle_close,
                                "fib_0786": entry,
                                "sl": sl,
                                "target": target_126,
                                "decline_pct": decline_pct,
                                "swing_days": swing_days,
                                "lower_wick_pct": lower_wick_pct,
                                "compression_3v10": compression,
                                "close_vs_786_pct": close_above,
                                "high_date": pd.Timestamp(high_date).date().isoformat(),
                                "low_date": pd.Timestamp(low_date).date().isoformat(),
                                "signal_timing": "after completed daily candle",
                                "entry_timing": "next session",
                            }

                        if (
                            close_above >= S05_MIN_CLOSE_ABOVE_786_PCT
                            and body_pct >= S05_MIN_BODY_PCT_RANGE
                        ):
                            strategy05_candidate = {
                                "symbol": symbol,
                                "signal_date": pd.Timestamp(date).date().isoformat(),
                                "close": candle_close,
                                "open": candle_open,
                                "high": candle_high,
                                "low": candle_low,
                                "fib_0786": entry,
                                "sl": sl,
                                "target_126": target_126,
                                "target_150": target_150,
                                "close_vs_786_pct": close_above,
                                "body_pct_range": body_pct,
                                "candle_direction": (
                                    "BULLISH"
                                    if candle_close > candle_open
                                    else "BEARISH"
                                    if candle_close < candle_open
                                    else "DOJI"
                                ),
                                "decline_pct": decline_pct,
                                "swing_days": swing_days,
                                "recovery_days": recovery_days,
                                "rsi14": _rsi14_last(closes),
                                "high_date": pd.Timestamp(high_date).date().isoformat(),
                                "swing_high": high_price,
                                "low_date": pd.Timestamp(low_date).date().isoformat(),
                                "swing_low": low_price,
                                "signal_timing": "after completed daily candle",
                                "entry_timing": "next session",
                            }

                if candle_low <= sl or candle_high >= target_126:
                    state = 0
                    high_price = candle_high
                    high_date = date
                    low_price = None
                    low_date = None
                    low_idx = None
                    entry = None
                    sl = None
                    target_126 = None
                    entry_date = None
                else:
                    state = 2

        elif state == 2:
            if candle_low <= sl or candle_high >= target_126:
                state = 0
                high_price = candle_high
                high_date = date
                low_price = None
                low_date = None
                low_idx = None
                entry = None
                sl = None
                target_126 = None
                entry_date = None

    classic_setup = None

    if state == 1:
        price_range = high_price - low_price
        classic_setup = {
            "Structure": "TRACKING",
            "High Date": pd.Timestamp(high_date).date(),
            "High": high_price,
            "Low Date": pd.Timestamp(low_date).date(),
            "Low": low_price,
            "Entry Date": None,
            "Entry": low_price + price_range * FIB_ENTRY,
            "SL": low_price + price_range * FIB_SL,
            "Target": low_price + price_range * FIB_TARGET_126,
        }

    elif state == 2:
        classic_setup = {
            "Structure": "OPEN",
            "High Date": pd.Timestamp(high_date).date(),
            "High": high_price,
            "Low Date": pd.Timestamp(low_date).date(),
            "Low": low_price,
            "Entry Date": (
                pd.Timestamp(entry_date).date()
                if entry_date is not None
                else None
            ),
            "Entry": entry,
            "SL": sl,
            "Target": target_126,
        }

    return classic_setup, premium_candidate, strategy05_candidate


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


def scan_market_once(market, symbols):
    started = time.time()

    classic_rows = []
    premium_candidates = []
    strategy05_candidates = []
    failed = []

    latest_market_date = None
    scan_time = now_ist().isoformat()

    for symbol in symbols:
        raw = market.get(symbol)

        if raw is None or raw.empty:
            failed.append(symbol)
            continue

        completed = completed_daily(raw)

        if completed is None or len(completed) < 40:
            failed.append(symbol)
            continue

        try:
            setup, premium, strategy05 = analyze_stock_fast(
                symbol,
                completed,
            )

            latest_price = float(raw["Close"].iloc[-1])
            status, distance = classic_classify(setup, latest_price)

            classic_rows.append({
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

            if premium is not None:
                premium_candidates.append(premium)

            if strategy05 is not None:
                strategy05_candidates.append(strategy05)

            d = pd.Timestamp(completed["Date"].iloc[-1]).date()
            if latest_market_date is None or d > latest_market_date:
                latest_market_date = d

        except Exception as exc:
            failed.append(symbol)
            if len(failed) <= 10:
                print("Analyze failed:", symbol, str(exc)[:120])

    print(
        "One-pass strategy calculation:",
        round(time.time() - started, 2),
        "sec",
    )

    return {
        "classic_rows": classic_rows,
        "premium_candidates": premium_candidates,
        "strategy05_candidates": strategy05_candidates,
        "failed": failed,
        "latest_market_date": latest_market_date,
        "scan_time": scan_time,
        "duration_seconds": time.time() - started,
    }


def _strategy_meta_key(name):
    return "strategy_generation:" + name


def _is_current(cache, strategy, generation, required_files):
    if not generation:
        return False

    cached_generation = cache.get_meta(_strategy_meta_key(strategy))

    if str(cached_generation or "") != str(generation):
        return False

    return all(Path(p).exists() for p in required_files)


def _mark_current(cache, strategies, generation):
    for name in strategies:
        cache.set_meta(_strategy_meta_key(name), generation)


def write_classic(scan):
    df = pd.DataFrame(scan["classic_rows"])

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
        df = (
            df.sort_values(
                ["_Priority", "Distance %"],
                na_position="last",
            )
            .drop(columns=["_Priority"])
        )

    df.to_csv(CLASSIC_OUTPUT, index=False)
    df.to_csv(LATEST_OUTPUT, index=False)
    pd.DataFrame({"Symbol": scan["failed"]}).to_csv(
        FAILED_OUTPUT,
        index=False,
    )

    # Keep the existing Clean/Premium ranking definitions untouched.
    subprocess.check_call([sys.executable, "fibedge_quality_live_merge.py"])
    subprocess.check_call([sys.executable, "fibedge_opportunity_rank_v3.py"])


def write_premium_plus(scan):
    candidates = list(scan["premium_candidates"])
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
        "scan_started_at_ist": scan["scan_time"],
        "scan_finished_at_ist": finished.isoformat(),
        "market_date": (
            scan["latest_market_date"].isoformat()
            if scan["latest_market_date"]
            else None
        ),
        "candidate_count": len(candidates),
        "cache_window": "1y",
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
    PREMIUM_PLUS_OUTPUT.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    pd.DataFrame({"Symbol": scan["failed"]}).to_csv(
        PREMIUM_PLUS_FAILED,
        index=False,
    )


def write_strategy05(scan):
    candidates = list(scan["strategy05_candidates"])
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
        "scan_started_at_ist": scan["scan_time"],
        "scan_finished_at_ist": finished.isoformat(),
        "market_date": (
            scan["latest_market_date"].isoformat()
            if scan["latest_market_date"]
            else None
        ),
        "candidate_count": len(candidates),
        "cache_window": "1y",
        "scan_policy": {
            "automatic": "once after market close",
            "manual": "shared cache; completed daily candle only",
            "market_close_ist": "15:30",
            "daily_settle_buffer_ist": "15:40",
        },
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
    STRATEGY05_OUTPUT.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    pd.DataFrame({"Symbol": scan["failed"]}).to_csv(
        STRATEGY05_FAILED,
        index=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "strategy",
        nargs="?",
        default="ALL",
        choices=[
            "ALL",
            "CLASSIC",
            "CLEAN",
            "PREMIUM",
            "PREMIUMPLUS",
            "STRATEGY05",
        ],
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Force a new 1-year cache seed.",
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
    print("Fast path: zero Yahoo requests when today's cache is current")
    print()

    market, cache_stats = refresh_market_cache(
        symbols,
        force_full=args.full,
    )

    cache, _ = get_cache()
    generation = cache_stats.get("generation")

    requested_classic = args.strategy in (
        "ALL",
        "CLASSIC",
        "CLEAN",
        "PREMIUM",
    )
    requested_premium_plus = args.strategy in ("ALL", "PREMIUMPLUS")
    requested_strategy05 = args.strategy in ("ALL", "STRATEGY05")

    classic_current = (
        requested_classic
        and _is_current(
            cache,
            "CLASSIC_SOURCE",
            generation,
            [
                CLASSIC_OUTPUT,
                LATEST_OUTPUT,
                "FIBEDGE_TOP_CURRENT_SETUPS.csv",
                "FIBEDGE_BEST_OPPORTUNITIES_V3.csv",
            ],
        )
    )

    premium_current = (
        requested_premium_plus
        and _is_current(
            cache,
            "PREMIUMPLUS",
            generation,
            [PREMIUM_PLUS_OUTPUT],
        )
    )

    s05_current = (
        requested_strategy05
        and _is_current(
            cache,
            "STRATEGY05",
            generation,
            [STRATEGY05_OUTPUT],
        )
    )

    need_calculation = (
        (requested_classic and not classic_current)
        or (requested_premium_plus and not premium_current)
        or (requested_strategy05 and not s05_current)
    )

    scan = None

    if need_calculation:
        scan = scan_market_once(market, symbols)

        if requested_classic and not classic_current:
            write_classic(scan)
            _mark_current(
                cache,
                ["CLASSIC_SOURCE", "CLASSIC", "CLEAN", "PREMIUM"],
                generation,
            )

        if requested_premium_plus and not premium_current:
            write_premium_plus(scan)
            _mark_current(cache, ["PREMIUMPLUS"], generation)

        if requested_strategy05 and not s05_current:
            write_strategy05(scan)
            _mark_current(cache, ["STRATEGY05"], generation)

    else:
        print("Strategy calculation: SKIPPED (same market generation already built)")

    total = time.time() - started

    summary = {
        "strategy": args.strategy,
        "finished_at_ist": now_ist().isoformat(),
        "structure_window": "1y",
        "cache": cache_stats,
        "strategy_calculation_skipped": not need_calculation,
        "strategy_calculation_seconds": (
            scan["duration_seconds"]
            if scan is not None
            else 0.0
        ),
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
    print("Yahoo skipped:", "YES" if cache_stats.get("network_skipped") else "NO")
    print(
        "Strategy calculation skipped:",
        "YES" if not need_calculation else "NO",
    )
    print("Total:", round(total, 2), "sec")
    print("Under 3 minutes:", "YES" if total < 180 else "NO")
    print("Cache backend:", cache_stats.get("backend"))
    print("=" * 92)


if __name__ == "__main__":
    main()

import json
import math
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

UNIVERSE_FILE = "NSE_STOCK_UNIVERSE.csv"
OUTPUT_FILE = Path("archive/premium_v1/data/premium_plus_candidates.json")
FAILED_FILE = Path("archive/premium_v1/data/premium_plus_failed_symbols.csv")

PERIOD = "5y"
BATCH_SIZE = 75

BASE_MIN_DECLINE = 0.08
PREMIUM_MIN_DECLINE_PCT = 15.0
MIN_SWING_DAYS = 15
MAX_LOWER_WICK_PCT = 10.0
MAX_COMPRESSION_3V10 = 0.90
MIN_CLOSE_ABOVE_786_PCT = 2.0

FIB_ENTRY = 0.786
FIB_SL = 0.500
FIB_TARGET = 1.260

IST = timezone(timedelta(hours=5, minutes=30))
SETTLE_HOUR = 15
SETTLE_MINUTE = 40


def now_ist():
    return datetime.now(IST)


def trim_completed(df):
    current = now_ist()
    today = pd.Timestamp(current.date())
    if (current.hour, current.minute) < (SETTLE_HOUR, SETTLE_MINUTE):
        df = df[df["Date"].dt.normalize() < today].copy()
    return df.reset_index(drop=True)


def extract_symbol(downloaded, symbol):
    if downloaded is None or downloaded.empty:
        return None
    try:
        if isinstance(downloaded.columns, pd.MultiIndex):
            if symbol not in downloaded.columns.get_level_values(1):
                return None
            df = downloaded.xs(symbol, axis=1, level=1).copy()
        else:
            df = downloaded.copy()

        df = df.dropna(how="all").reset_index()
        if df.empty:
            return None

        df.rename(columns={df.columns[0]: "Date"}, inplace=True)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = (
            df.dropna(subset=["Date", "Open", "High", "Low", "Close"])
            .sort_values("Date")
            .reset_index(drop=True)
        )
        return trim_completed(df)
    except Exception:
        return None


def true_range(df):
    prev_close = df["Close"].shift(1)
    return pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def find_candidate(symbol, df):
    if df is None or len(df) < 40:
        return None

    tr = true_range(df)
    atr3 = tr.rolling(3, min_periods=3).mean()
    atr10 = tr.rolling(10, min_periods=10).mean()

    state = "SEARCH_HIGH"
    high_price = float(df.loc[0, "High"])
    high_date = df.loc[0, "Date"]
    low_price = None
    low_date = None
    low_idx = None
    sl = entry = target = None
    last_idx = len(df) - 1

    for i in range(1, len(df)):
        date = df.loc[i, "Date"]
        hi = float(df.loc[i, "High"])
        lo = float(df.loc[i, "Low"])

        if state == "SEARCH_HIGH":
            if hi > high_price:
                high_price = hi
                high_date = date

            decline = (high_price - lo) / high_price
            days = (date - high_date).days
            if decline >= BASE_MIN_DECLINE and days >= MIN_SWING_DAYS:
                state = "TRACK_LOW"
                low_price = lo
                low_date = date
                low_idx = i

        elif state == "TRACK_LOW":
            if lo < low_price:
                low_price = lo
                low_date = date
                low_idx = i

            swing_range = high_price - low_price
            sl = low_price + swing_range * FIB_SL
            entry = low_price + swing_range * FIB_ENTRY
            target = low_price + swing_range * FIB_TARGET

            if i <= low_idx:
                continue

            if hi >= entry:
                if i == last_idx:
                    op = float(df.loc[i, "Open"])
                    cl = float(df.loc[i, "Close"])
                    rng = hi - lo
                    if rng <= 0:
                        return None

                    decline_pct = (high_price - low_price) / high_price * 100.0
                    lower_wick = min(op, cl) - lo
                    lower_wick_pct = max(lower_wick, 0.0) / rng * 100.0
                    compression = (
                        float(atr3.iloc[i] / atr10.iloc[i])
                        if pd.notna(atr3.iloc[i]) and pd.notna(atr10.iloc[i]) and atr10.iloc[i] != 0
                        else np.nan
                    )
                    close_above = (cl / entry - 1.0) * 100.0
                    swing_days = int((low_date - high_date).days)

                    if (
                        decline_pct >= PREMIUM_MIN_DECLINE_PCT
                        and swing_days >= MIN_SWING_DAYS
                        and lower_wick_pct <= MAX_LOWER_WICK_PCT
                        and np.isfinite(compression)
                        and compression <= MAX_COMPRESSION_3V10
                        and close_above >= MIN_CLOSE_ABOVE_786_PCT
                    ):
                        return {
                            "symbol": symbol,
                            "signal_date": date.date().isoformat(),
                            "close": cl,
                            "fib_0786": entry,
                            "sl": sl,
                            "target": target,
                            "decline_pct": decline_pct,
                            "swing_days": swing_days,
                            "lower_wick_pct": lower_wick_pct,
                            "compression_3v10": compression,
                            "close_vs_786_pct": close_above,
                            "high_date": high_date.date().isoformat(),
                            "low_date": low_date.date().isoformat(),
                            "signal_timing": "after completed daily candle",
                            "entry_timing": "next session",
                        }

                if lo <= sl or hi >= target:
                    state = "SEARCH_HIGH"
                    high_price = hi
                    high_date = date
                    low_price = low_date = low_idx = None
                    sl = entry = target = None
                else:
                    state = "OPEN"

        elif state == "OPEN":
            if lo <= sl or hi >= target:
                state = "SEARCH_HIGH"
                high_price = hi
                high_date = date
                low_price = low_date = low_idx = None
                sl = entry = target = None

    return None


def main():
    started = now_ist()
    universe = pd.read_csv(UNIVERSE_FILE)
    symbols = universe["YF_SYMBOL"].dropna().astype(str).str.strip().drop_duplicates().tolist()

    candidates = []
    failed = []
    latest_market_date = None
    total_batches = math.ceil(len(symbols) / BATCH_SIZE)

    for batch_no, start in enumerate(range(0, len(symbols), BATCH_SIZE), 1):
        batch = symbols[start:start+BATCH_SIZE]
        print(f"Premium+ batch {batch_no}/{total_batches} ({len(batch)} symbols)")

        try:
            daily = yf.download(
                batch,
                period=PERIOD,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="column",
            )
        except Exception as exc:
            print("Batch failed:", exc)
            failed.extend(batch)
            continue

        for symbol in batch:
            df = extract_symbol(daily, symbol)
            if df is None or df.empty:
                failed.append(symbol)
                continue

            d = pd.Timestamp(df["Date"].iloc[-1]).date()
            if latest_market_date is None or d > latest_market_date:
                latest_market_date = d

            try:
                candidate = find_candidate(symbol, df)
                if candidate:
                    candidates.append(candidate)
            except Exception:
                failed.append(symbol)

        print("  candidates:", len(candidates), "| failed:", len(failed))
        time.sleep(0.5)

    candidates.sort(key=lambda r: (-r["close_vs_786_pct"], r["symbol"]))
    finished = now_ist()

    payload = {
        "strategy": "FibEdge Premium+ V1",
        "updated_at": finished.isoformat(),
        "scan_started_at_ist": started.isoformat(),
        "scan_finished_at_ist": finished.isoformat(),
        "market_date": latest_market_date.isoformat() if latest_market_date else None,
        "candidate_count": len(candidates),
        "frozen_rules": {
            "base_min_decline_pct": 8,
            "premium_min_decline_pct": 15,
            "min_swing_days": 15,
            "max_lower_wick_pct": 10,
            "max_compression_3v10": 0.9,
            "min_close_above_786_pct": 2,
            "signal_timing": "after completed daily candle",
            "entry_timing": "next session",
        },
        "candidates": candidates,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    pd.DataFrame({"Symbol": failed}).to_csv(FAILED_FILE, index=False)

    print("Premium+ candidates:", len(candidates))
    print("Market date:", payload["market_date"])
    print("Scan finished IST:", payload["scan_finished_at_ist"])


if __name__ == "__main__":
    main()

import json
import math
import time
from datetime import datetime, time as dtime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

UNIVERSE_FILE = "NSE_STOCK_UNIVERSE.csv"
OUTPUT_FILE = Path("strategy_05_live/data/strategy_05_candidates.json")
FAILED_FILE = Path("strategy_05_live/data/strategy_05_failed_symbols.csv")

PERIOD = "5y"
BATCH_SIZE = 75

MIN_DECLINE = 0.08
MIN_SWING_DAYS = 15

FIB_ENTRY = 0.786
FIB_SL = 0.500
FIB_TARGET_126 = 1.260
FIB_TARGET_150 = 1.500

MIN_CLOSE_ABOVE_786_PCT = 4.0
MIN_BODY_PCT_RANGE = 60.0

IST = timezone(timedelta(hours=5, minutes=30))
MARKET_CLOSE = dtime(15, 30)
DAILY_SETTLE_BUFFER = dtime(15, 40)


def now_ist():
    return datetime.now(IST)


def trim_to_completed_daily(df):
    """Never treat the current intraday daily candle as completed.

    Before 15:40 IST, today's Yahoo daily bar is removed if present.
    After 15:40 IST, today's bar is allowed. This protects manual scans
    from accidentally using a partial daily candle.
    """
    if df is None or df.empty:
        return df

    current = now_ist()
    today = pd.Timestamp(current.date())

    if current.time() < DAILY_SETTLE_BUFFER:
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

        df = df.dropna(how="all")
        if df.empty:
            return None

        df = df.reset_index()
        date_col = df.columns[0]
        df.rename(columns={date_col: "Date"}, inplace=True)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = (
            df.dropna(subset=["Date", "Open", "High", "Low", "Close"])
            .sort_values("Date")
            .reset_index(drop=True)
        )
        return trim_to_completed_daily(df)

    except Exception:
        return None


def rsi14(close):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(14, min_periods=14).mean()
    avg_loss = loss.rolling(14, min_periods=14).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    value = 100 - (100 / (1 + rs))

    if value.empty or pd.isna(value.iloc[-1]):
        return None

    return float(value.iloc[-1])


def find_latest_signal(symbol, df):
    if df is None or len(df) < 40:
        return None

    state = "SEARCH_HIGH"
    high_price = float(df.loc[0, "High"])
    high_date = df.loc[0, "Date"]

    low_price = None
    low_date = None
    low_idx = None

    entry = None
    sl = None
    target_126 = None

    last_idx = len(df) - 1

    for i in range(1, len(df)):
        date = df.loc[i, "Date"]
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
            target_126 = low_price + price_range * FIB_TARGET_126

            if i <= low_idx:
                continue

            if candle_high >= entry:
                if i == last_idx:
                    candle_open = float(df.loc[i, "Open"])
                    candle_close = float(df.loc[i, "Close"])
                    candle_range = candle_high - candle_low

                    if candle_range <= 0:
                        return None

                    body_pct = abs(candle_close - candle_open) / candle_range * 100.0
                    close_above_pct = (candle_close / entry - 1.0) * 100.0

                    if (
                        close_above_pct >= MIN_CLOSE_ABOVE_786_PCT
                        and body_pct >= MIN_BODY_PCT_RANGE
                    ):
                        target_150 = low_price + price_range * FIB_TARGET_150

                        return {
                            "symbol": symbol,
                            "signal_date": date.date().isoformat(),
                            "close": candle_close,
                            "open": candle_open,
                            "high": candle_high,
                            "low": candle_low,
                            "fib_0786": entry,
                            "sl": sl,
                            "target_126": target_126,
                            "target_150": target_150,
                            "close_vs_786_pct": close_above_pct,
                            "body_pct_range": body_pct,
                            "candle_direction": (
                                "BULLISH"
                                if candle_close > candle_open
                                else "BEARISH"
                                if candle_close < candle_open
                                else "DOJI"
                            ),
                            "decline_pct": (high_price - low_price) / high_price * 100.0,
                            "swing_days": int((low_date - high_date).days),
                            "recovery_days": int((date - low_date).days),
                            "rsi14": rsi14(df["Close"]),
                            "high_date": high_date.date().isoformat(),
                            "swing_high": high_price,
                            "low_date": low_date.date().isoformat(),
                            "swing_low": low_price,
                            "signal_timing": "after completed daily candle",
                            "entry_timing": "next session",
                        }

                if candle_low <= sl or candle_high >= target_126:
                    state = "SEARCH_HIGH"
                    high_price = candle_high
                    high_date = date
                    low_price = None
                    low_date = None
                    low_idx = None
                    entry = None
                    sl = None
                    target_126 = None
                else:
                    state = "OPEN"

        elif state == "OPEN":
            if candle_low <= sl or candle_high >= target_126:
                state = "SEARCH_HIGH"
                high_price = candle_high
                high_date = date
                low_price = None
                low_date = None
                low_idx = None
                entry = None
                sl = None
                target_126 = None

    return None


def main():
    started = now_ist()
    universe = pd.read_csv(UNIVERSE_FILE)

    symbols = (
        universe["YF_SYMBOL"]
        .dropna()
        .astype(str)
        .str.strip()
        .drop_duplicates()
        .tolist()
    )

    candidates = []
    failed = []
    latest_completed_market_date = None

    total_batches = math.ceil(len(symbols) / BATCH_SIZE)

    for batch_no, start in enumerate(range(0, len(symbols), BATCH_SIZE), 1):
        batch = symbols[start:start + BATCH_SIZE]
        print(f"Strategy 05 batch {batch_no}/{total_batches} ({len(batch)} symbols)")

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

            this_date = pd.Timestamp(df["Date"].iloc[-1]).date()
            if latest_completed_market_date is None or this_date > latest_completed_market_date:
                latest_completed_market_date = this_date

            try:
                result = find_latest_signal(symbol, df)
                if result is not None:
                    candidates.append(result)
            except Exception:
                failed.append(symbol)

        print("  candidates:", len(candidates), "| failed:", len(failed))
        time.sleep(0.5)

    candidates.sort(
        key=lambda r: (
            -float(r["close_vs_786_pct"]),
            -float(r["body_pct_range"]),
            r["symbol"],
        )
    )

    finished = now_ist()

    payload = {
        "strategy": "FibEdge Confirmed Continuation",
        "updated_at": finished.isoformat(),
        "scan_started_at_ist": started.isoformat(),
        "scan_finished_at_ist": finished.isoformat(),
        "market_date": (
            latest_completed_market_date.isoformat()
            if latest_completed_market_date
            else None
        ),
        "candidate_count": len(candidates),
        "scan_policy": {
            "automatic": "once after market close",
            "manual": "allowed; partial current-day candles are ignored before 15:40 IST",
            "market_close_ist": "15:30",
            "daily_settle_buffer_ist": "15:40",
        },
        "frozen_rule": {
            "fib_entry": FIB_ENTRY,
            "fib_stop": FIB_SL,
            "primary_target": FIB_TARGET_126,
            "extension_target": FIB_TARGET_150,
            "min_close_above_786_pct": MIN_CLOSE_ABOVE_786_PCT,
            "min_body_pct_range": MIN_BODY_PCT_RANGE,
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

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    pd.DataFrame({"Symbol": failed}).to_csv(FAILED_FILE, index=False)

    print()
    print("=" * 90)
    print("STRATEGY 05 CONFIRMED CONTINUATION")
    print("=" * 90)
    print("Universe:", len(symbols))
    print("Market date:", payload["market_date"])
    print("Scan finished IST:", payload["scan_finished_at_ist"])
    print("Candidates:", len(candidates))
    print("Failed:", len(failed))
    print("Saved:", OUTPUT_FILE)
    print("=" * 90)


if __name__ == "__main__":
    main()

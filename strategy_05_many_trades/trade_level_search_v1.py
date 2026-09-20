import itertools
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

UNIVERSE_FILE = "NSE_STOCK_UNIVERSE.csv"
OUT_DIR = Path("strategy_05_many_trades/results")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PERIOD = "5y"
BATCH_SIZE = 75

FIB_ENTRY = 0.786
FIB_SL = 0.500
FIB_TARGET = 1.260

BASE_MIN_DECLINE = 0.08
BASE_MIN_SWING_DAYS = 15
MAX_HOLD_CALENDAR_DAYS = 60

DEV_END = pd.Timestamp("2024-12-31")

DECLINE_MIN_GRID = [8, 10, 12, 15]
SWING_MIN_GRID = [15, 20, 30, 40]
RECOVERY_MAX_GRID = [None, 120, 90, 60, 45, 30]
CLOSE_ABOVE_ENTRY_MIN_GRID = [None, 0.0, 0.5, 1.0, 2.0]
CLOSE_LOCATION_MIN_GRID = [None, 55, 60, 65, 70]
LOWER_WICK_MAX_GRID = [None, 35, 25, 20, 15, 10]

MIN_DEV_RESOLVED = 400
TOP_DEV_RULES_TO_VALIDATE = 100


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
        for c in ["Open", "High", "Low", "Close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.dropna(subset=["Date", "Open", "High", "Low", "Close"]).reset_index(drop=True)
    except Exception:
        return None


def safe_range(row):
    return max(float(row["High"]) - float(row["Low"]), 1e-12)


def signal_features(df, i, high_price, high_date, low_price, low_date, entry):
    row = df.loc[i]
    rng = safe_range(row)
    lower_wick = max(0.0, min(float(row["Open"]), float(row["Close"])) - float(row["Low"]))
    close_location = (float(row["Close"]) - float(row["Low"])) / rng * 100.0

    return {
        "Decline %": (high_price - low_price) / high_price * 100.0,
        "Swing Days": int((low_date - high_date).days),
        "Recovery Days": int((row["Date"] - low_date).days),
        "Close Above Entry %": (float(row["Close"]) - entry) / entry * 100.0,
        "Close Location %": close_location,
        "Lower Wick %": lower_wick / rng * 100.0,
    }


def backtest_symbol(symbol, df):
    trades = []
    if df is None or len(df) < 45:
        return trades

    state = "SEARCH_HIGH"
    high_price = float(df.loc[0, "High"])
    high_date = df.loc[0, "Date"]

    low_price = low_date = low_idx = None
    entry = sl = target = None
    entry_date = None
    features = None

    def reset_from(i):
        nonlocal state, high_price, high_date
        nonlocal low_price, low_date, low_idx
        nonlocal entry, sl, target, entry_date, features
        state = "SEARCH_HIGH"
        high_price = float(df.loc[i, "High"])
        high_date = df.loc[i, "Date"]
        low_price = low_date = low_idx = None
        entry = sl = target = None
        entry_date = None
        features = None

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

            if decline >= BASE_MIN_DECLINE and days >= BASE_MIN_SWING_DAYS:
                state = "TRACK_LOW"
                low_price = lo
                low_date = date
                low_idx = i

        elif state == "TRACK_LOW":
            if lo < low_price:
                low_price = lo
                low_date = date
                low_idx = i

            price_range = high_price - low_price
            sl = low_price + price_range * FIB_SL
            entry = low_price + price_range * FIB_ENTRY
            target = low_price + price_range * FIB_TARGET

            if i <= low_idx:
                continue

            if hi >= entry:
                entry_date = date
                features = signal_features(
                    df, i, high_price, high_date, low_price, low_date, entry
                )

                # Conservative daily-candle handling:
                # if stop and entry coexist on the signal candle, count LOSS first.
                if lo <= sl:
                    outcome = "LOSS"
                elif hi >= target:
                    outcome = "WIN"
                else:
                    outcome = None

                if outcome is not None:
                    trades.append({
                        "Symbol": symbol,
                        "High Date": high_date,
                        "Low Date": low_date,
                        "Entry Date": entry_date,
                        "Exit Date": date,
                        "Entry": entry,
                        "SL": sl,
                        "Target": target,
                        "Outcome": outcome,
                        "Hold Days": 0,
                        **features,
                    })
                    reset_from(i)
                else:
                    state = "OPEN"

        elif state == "OPEN":
            held = (date - entry_date).days
            hit_sl = lo <= sl
            hit_target = hi >= target

            if hit_sl or hit_target or held >= MAX_HOLD_CALENDAR_DAYS:
                if hit_sl:
                    outcome = "LOSS"
                elif hit_target:
                    outcome = "WIN"
                else:
                    outcome = "TIMEOUT"

                trades.append({
                    "Symbol": symbol,
                    "High Date": high_date,
                    "Low Date": low_date,
                    "Entry Date": entry_date,
                    "Exit Date": date,
                    "Entry": entry,
                    "SL": sl,
                    "Target": target,
                    "Outcome": outcome,
                    "Hold Days": held,
                    **features,
                })
                reset_from(i)

    return trades


def apply_rule(df, rule):
    x = df.copy()
    x = x[x["Decline %"] >= rule["decline_min"]]
    x = x[x["Swing Days"] >= rule["swing_min"]]

    if rule["recovery_max"] is not None:
        x = x[x["Recovery Days"] <= rule["recovery_max"]]
    if rule["close_above_min"] is not None:
        x = x[x["Close Above Entry %"] >= rule["close_above_min"]]
    if rule["close_location_min"] is not None:
        x = x[x["Close Location %"] >= rule["close_location_min"]]
    if rule["lower_wick_max"] is not None:
        x = x[x["Lower Wick %"] <= rule["lower_wick_max"]]

    return x


def summarize(df):
    resolved = df[df["Outcome"].isin(["WIN", "LOSS"])]
    wins = int((resolved["Outcome"] == "WIN").sum())
    losses = int((resolved["Outcome"] == "LOSS").sum())
    return {
        "Trades": len(df),
        "Resolved": len(resolved),
        "Wins": wins,
        "Losses": losses,
        "Timeouts": int((df["Outcome"] == "TIMEOUT").sum()),
        "Win Rate %": wins / len(resolved) * 100.0 if len(resolved) else np.nan,
        "Unique Stocks": int(resolved["Symbol"].nunique()) if len(resolved) else 0,
    }


def wilson_lower(wins, n, z=1.96):
    if n <= 0:
        return np.nan
    p = wins / n
    den = 1 + z*z/n
    centre = p + z*z/(2*n)
    adj = z * math.sqrt((p*(1-p) + z*z/(4*n))/n)
    return (centre - adj) / den * 100.0


def main():
    universe = pd.read_csv(UNIVERSE_FILE)
    symbols = (
        universe["YF_SYMBOL"]
        .dropna()
        .astype(str)
        .str.strip()
        .drop_duplicates()
        .tolist()
    )

    all_trades = []
    failed = []

    total_batches = math.ceil(len(symbols) / BATCH_SIZE)

    for batch_no, start in enumerate(range(0, len(symbols), BATCH_SIZE), 1):
        batch = symbols[start:start+BATCH_SIZE]
        print(f"Batch {batch_no}/{total_batches} ({len(batch)} symbols)")

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
            print("Batch download failed:", exc)
            failed.extend(batch)
            continue

        for symbol in batch:
            df = extract_symbol(daily, symbol)
            if df is None:
                failed.append(symbol)
                continue
            try:
                all_trades.extend(backtest_symbol(symbol, df))
            except Exception:
                failed.append(symbol)

        print("Trades so far:", len(all_trades), "| Failed:", len(failed))
        time.sleep(0.7)

    trades = pd.DataFrame(all_trades)
    trades.to_csv(OUT_DIR / "all_base_trades_v1.csv", index=False)
    pd.DataFrame({"Symbol": failed}).to_csv(OUT_DIR / "failed_symbols_v1.csv", index=False)

    if trades.empty:
        print("No trades produced.")
        return

    trades["Entry Date"] = pd.to_datetime(trades["Entry Date"])
    dev = trades[trades["Entry Date"] <= DEV_END].copy()
    test = trades[trades["Entry Date"] > DEV_END].copy()

    print("\nBASE ALL:", summarize(trades))
    print("DEV:", summarize(dev))
    print("TEST:", summarize(test))

    rows = []
    for vals in itertools.product(
        DECLINE_MIN_GRID,
        SWING_MIN_GRID,
        RECOVERY_MAX_GRID,
        CLOSE_ABOVE_ENTRY_MIN_GRID,
        CLOSE_LOCATION_MIN_GRID,
        LOWER_WICK_MAX_GRID,
    ):
        rule = {
            "decline_min": vals[0],
            "swing_min": vals[1],
            "recovery_max": vals[2],
            "close_above_min": vals[3],
            "close_location_min": vals[4],
            "lower_wick_max": vals[5],
        }
        z = apply_rule(dev, rule)
        stats = summarize(z)

        if stats["Resolved"] < MIN_DEV_RESOLVED:
            continue

        rows.append({
            **rule,
            **stats,
            "Wilson Lower 95 %": wilson_lower(stats["Wins"], stats["Resolved"]),
        })

    frontier = pd.DataFrame(rows)
    if frontier.empty:
        print("No development rule reached MIN_DEV_RESOLVED.")
        return

    frontier = frontier.sort_values(
        ["Win Rate %", "Resolved", "Wilson Lower 95 %"],
        ascending=[False, False, False],
    )
    frontier.to_csv(OUT_DIR / "dev_rule_frontier_v1.csv", index=False)

    validation = []
    for _, rule_row in frontier.head(TOP_DEV_RULES_TO_VALIDATE).iterrows():
        rule = {
            "decline_min": rule_row["decline_min"],
            "swing_min": rule_row["swing_min"],
            "recovery_max": None if pd.isna(rule_row["recovery_max"]) else rule_row["recovery_max"],
            "close_above_min": None if pd.isna(rule_row["close_above_min"]) else rule_row["close_above_min"],
            "close_location_min": None if pd.isna(rule_row["close_location_min"]) else rule_row["close_location_min"],
            "lower_wick_max": None if pd.isna(rule_row["lower_wick_max"]) else rule_row["lower_wick_max"],
        }

        dev_stats = summarize(apply_rule(dev, rule))
        test_stats = summarize(apply_rule(test, rule))
        all_stats = summarize(apply_rule(trades, rule))

        validation.append({
            **rule,
            "Dev Resolved": dev_stats["Resolved"],
            "Dev Win Rate %": dev_stats["Win Rate %"],
            "Test Resolved": test_stats["Resolved"],
            "Test Win Rate %": test_stats["Win Rate %"],
            "All Resolved": all_stats["Resolved"],
            "All Win Rate %": all_stats["Win Rate %"],
            "Unique Stocks": all_stats["Unique Stocks"],
            "Test Wilson Lower 95 %": wilson_lower(test_stats["Wins"], test_stats["Resolved"]),
        })

    val = pd.DataFrame(validation).sort_values(
        ["Test Win Rate %", "All Resolved"],
        ascending=[False, False],
    )
    val.to_csv(OUT_DIR / "validation_top_rules_v1.csv", index=False)

    print("\nTop development rules:")
    print(frontier.head(15).to_string(index=False))

    print("\nUntouched test validation of top development rules:")
    print(val.head(20).to_string(index=False))

    good = val[
        (val["Test Win Rate %"] >= 70)
        & (val["All Resolved"] >= 1000)
    ].copy()

    print("\n70%+ TEST and 1000+ ALL RESOLVED:")
    if good.empty:
        print("None found in V1 grid.")
    else:
        print(good.head(20).to_string(index=False))


if __name__ == "__main__":
    main()

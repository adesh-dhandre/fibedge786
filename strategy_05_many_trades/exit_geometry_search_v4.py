import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

RESULTS = Path("strategy_05_many_trades/results")
TRADES_FILE = RESULTS / "all_base_trades_enriched_v3.csv"

BATCH_SIZE = 75
PERIOD = "5y"
MAX_HOLD_CALENDAR_DAYS = 60
DEV_END = pd.Timestamp("2024-12-31")

# Entry remains locked at Fib 0.786.
# We now test whether the original 1.260 target is the main reason
# high-volume hit-rate cannot reach 70%.
TARGET_FIB_GRID = [1.05, 1.10, 1.15, 1.20, 1.26]
STOP_FIB_GRID = [0.50]

# Broad candidate selectors discovered in V3.
FILTERS = {
    "BASE": lambda d: pd.Series(True, index=d.index),
    "CLOSE3_UP4OF5": lambda d: (
        (d["Close Above Entry %"] >= 3.0)
        & (d["Up Close Ratio 5"] >= 0.8)
    ),
    "CLOSE3_UP4OF5_REC90": lambda d: (
        (d["Close Above Entry %"] >= 3.0)
        & (d["Up Close Ratio 5"] >= 0.8)
        & (d["Recovery Days"] <= 90)
    ),
    "CLOSE2.5_UP4OF5": lambda d: (
        (d["Close Above Entry %"] >= 2.5)
        & (d["Up Close Ratio 5"] >= 0.8)
    ),
    "CLOSE2_UP4OF5": lambda d: (
        (d["Close Above Entry %"] >= 2.0)
        & (d["Up Close Ratio 5"] >= 0.8)
    ),
}

MIN_ALL_RESOLVED = 1000
TARGET_LATER_WR = 70.0


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


def simulate_one(row, df, stop_fib, target_fib):
    high = float(row["High"])
    low = float(row["Low"])
    entry_date = pd.Timestamp(row["Entry Date"]).normalize()

    price_range = high - low
    if not np.isfinite(price_range) or price_range <= 0:
        return None

    entry = low + price_range * 0.786
    sl = low + price_range * stop_fib
    target = low + price_range * target_fib

    # Start from the original signal/entry day.
    after = df[df["Date"] >= entry_date].copy()
    if after.empty:
        return None

    for _, bar in after.iterrows():
        date = pd.Timestamp(bar["Date"]).normalize()
        if (date - entry_date).days > MAX_HOLD_CALENDAR_DAYS:
            return {
                "Outcome": "TIMEOUT",
                "Exit Date": date,
                "Hold Days": (date - entry_date).days,
            }

        hi = float(bar["High"])
        lo = float(bar["Low"])

        hit_sl = lo <= sl
        hit_target = hi >= target

        # Conservative ambiguity handling: loss first.
        if hit_sl:
            return {
                "Outcome": "LOSS",
                "Exit Date": date,
                "Hold Days": (date - entry_date).days,
            }

        if hit_target:
            return {
                "Outcome": "WIN",
                "Exit Date": date,
                "Hold Days": (date - entry_date).days,
            }

    return {
        "Outcome": "TIMEOUT",
        "Exit Date": pd.NaT,
        "Hold Days": np.nan,
    }


def summarize(df):
    r = df[df["Outcome"].isin(["WIN", "LOSS"])]
    n = len(r)
    wins = int((r["Outcome"] == "WIN").sum())
    losses = int((r["Outcome"] == "LOSS").sum())
    return {
        "Resolved": n,
        "Wins": wins,
        "Losses": losses,
        "Timeouts": int((df["Outcome"] == "TIMEOUT").sum()),
        "WR %": wins / n * 100.0 if n else np.nan,
        "Unique Stocks": int(r["Symbol"].nunique()) if n else 0,
    }


def wilson_lower(wins, n, z=1.96):
    if n <= 0:
        return np.nan
    p = wins / n
    den = 1 + z*z/n
    centre = p + z*z/(2*n)
    adj = z * math.sqrt((p*(1-p) + z*z/(4*n))/n)
    return (centre - adj) / den * 100.0


def reward_risk(stop_fib, target_fib):
    risk = 0.786 - stop_fib
    reward = target_fib - 0.786
    return reward / risk if risk > 0 else np.nan


def breakeven_wr(rr):
    if not np.isfinite(rr) or rr <= 0:
        return np.nan
    return 100.0 / (1.0 + rr)


def main():
    if not TRADES_FILE.exists():
        raise SystemExit(
            f"Missing {TRADES_FILE}. Run V3 first."
        )

    trades = pd.read_csv(TRADES_FILE)
    trades["Entry Date"] = pd.to_datetime(trades["Entry Date"], errors="coerce").dt.normalize()

    symbols = sorted(trades["Symbol"].dropna().astype(str).unique().tolist())
    market = {}
    failed = []

    total_batches = math.ceil(len(symbols) / BATCH_SIZE)

    for batch_no, start in enumerate(range(0, len(symbols), BATCH_SIZE), 1):
        batch = symbols[start:start+BATCH_SIZE]
        print(f"Price batch {batch_no}/{total_batches} ({len(batch)} symbols)")

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
            print("  download failed:", exc)
            failed.extend(batch)
            continue

        for symbol in batch:
            df = extract_symbol(daily, symbol)
            if df is None:
                failed.append(symbol)
            else:
                market[symbol] = df

        print("  loaded:", len(market), "| failed:", len(failed))
        time.sleep(0.5)

    # Evaluate each geometry once for each historical trade, then apply filters.
    rows = []

    for stop_fib in STOP_FIB_GRID:
        for target_fib in TARGET_FIB_GRID:
            print(f"\nTesting stop={stop_fib:.3f} target={target_fib:.3f} ...")

            sims = []
            for idx, row in trades.iterrows():
                symbol = row["Symbol"]
                df = market.get(symbol)
                if df is None:
                    continue

                result = simulate_one(row, df, stop_fib, target_fib)
                if result is None:
                    continue

                sims.append({
                    "_idx": idx,
                    "Symbol": symbol,
                    "Entry Date": row["Entry Date"],
                    **result,
                })

            sim = pd.DataFrame(sims).set_index("_idx")
            base = trades.join(
                sim[["Outcome", "Exit Date", "Hold Days"]],
                how="inner",
                rsuffix="_SIM",
            )

            rr = reward_risk(stop_fib, target_fib)
            be = breakeven_wr(rr)

            for filter_name, filter_fn in FILTERS.items():
                selected = base[filter_fn(base).fillna(False)].copy()

                dev = selected[selected["Entry Date"] <= DEV_END]
                later = selected[selected["Entry Date"] > DEV_END]

                sd = summarize(dev)
                sl = summarize(later)
                sa = summarize(selected)

                expectancy_r = (
                    (sa["WR %"]/100.0) * rr
                    - (1.0 - sa["WR %"]/100.0)
                    if sa["Resolved"] else np.nan
                )

                rows.append({
                    "Filter": filter_name,
                    "Stop Fib": stop_fib,
                    "Target Fib": target_fib,
                    "Reward/Risk": rr,
                    "Breakeven WR %": be,
                    "Dev Resolved": sd["Resolved"],
                    "Dev WR %": sd["WR %"],
                    "Later Resolved": sl["Resolved"],
                    "Later WR %": sl["WR %"],
                    "Later Wilson Low %": wilson_lower(sl["Wins"], sl["Resolved"]),
                    "All Resolved": sa["Resolved"],
                    "All WR %": sa["WR %"],
                    "Unique Stocks": sa["Unique Stocks"],
                    "Expectancy R": expectancy_r,
                })

    out = pd.DataFrame(rows)
    out.to_csv(RESULTS / "v4_exit_geometry_all.csv", index=False)

    high_volume = out[out["All Resolved"] >= MIN_ALL_RESOLVED].copy()
    high_volume = high_volume.sort_values(
        ["Later WR %", "All Resolved", "Expectancy R"],
        ascending=[False, False, False],
    )
    high_volume.to_csv(
        RESULTS / "v4_high_volume_frontier.csv", index=False
    )

    target = high_volume[
        high_volume["Later WR %"] >= TARGET_LATER_WR
    ].copy()
    target.to_csv(RESULTS / "v4_target_hits.csv", index=False)

    positive = high_volume[
        high_volume["Expectancy R"] > 0
    ].copy()
    positive.to_csv(
        RESULTS / "v4_positive_expectancy_high_volume.csv", index=False
    )

    print("\n=== V4 TARGET: LATER WR >=70% AND ALL RESOLVED >=1000 ===")
    if target.empty:
        print("NONE")
    else:
        print(target.head(30).to_string(index=False))

    print("\n=== V4 HIGH-VOLUME FRONTIER ===")
    if high_volume.empty:
        print("NONE")
    else:
        print(high_volume.head(40).to_string(index=False))

    print("\n=== V4 POSITIVE-EXPECTANCY HIGH-VOLUME ===")
    if positive.empty:
        print("NONE")
    else:
        print(positive.head(40).to_string(index=False))


if __name__ == "__main__":
    main()

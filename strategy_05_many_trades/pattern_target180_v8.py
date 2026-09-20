import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

RESULTS = Path("strategy_05_many_trades/results")
FEATURE_FILE = RESULTS / "pattern_features_v6.csv"

PERIOD = "5y"
BATCH_SIZE = 75
MAX_HOLD_CALENDAR_DAYS = 60

FIB_ENTRY = 0.786
FIB_SL = 0.500
FIB_TARGET = 1.800

FILTERS = {
    "BODY60_CLOSE4": lambda d: (
        (d["SIG_BodyPct"] >= 60)
        & (d["SIG_CloseAbove786Pct"] >= 4.0)
    ),
    "BODY60_CLOSE4_RSI55": lambda d: (
        (d["SIG_BodyPct"] >= 60)
        & (d["SIG_CloseAbove786Pct"] >= 4.0)
        & (d["SIG_RSI14"] >= 55)
    ),
    "BODY50_CLOSE4": lambda d: (
        (d["SIG_BodyPct"] >= 50)
        & (d["SIG_CloseAbove786Pct"] >= 4.0)
    ),
    "CLOSE5_ONLY": lambda d: (
        d["SIG_CloseAbove786Pct"] >= 5.0
    ),
}

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

        return df.dropna(
            subset=["Date", "Open", "High", "Low", "Close"]
        ).sort_values("Date").reset_index(drop=True)

    except Exception:
        return None


def reconstruct_levels(row):
    entry = float(row["Entry"])
    sl = float(row["SL"])

    price_range = (entry - sl) / (FIB_ENTRY - FIB_SL)
    if not np.isfinite(price_range) or price_range <= 0:
        return None

    low = sl - price_range * FIB_SL
    target = low + price_range * FIB_TARGET

    return {
        "Entry": entry,
        "SL": sl,
        "Target": target,
    }


def simulate_from_next_session(row, df):
    levels = reconstruct_levels(row)
    if levels is None:
        return None

    signal_date = pd.Timestamp(row["Entry Date"]).normalize()
    matches = df.index[df["Date"].dt.normalize() == signal_date].tolist()
    if not matches:
        return None

    start_idx = matches[0] + 1
    if start_idx >= len(df):
        return None

    entry_date = pd.Timestamp(df.loc[start_idx, "Date"]).normalize()

    for j in range(start_idx, len(df)):
        bar = df.loc[j]
        date = pd.Timestamp(bar["Date"]).normalize()

        if (date - entry_date).days > MAX_HOLD_CALENDAR_DAYS:
            return {
                "Outcome180": "TIMEOUT",
                "Entry180Date": entry_date,
                "Exit180Date": date,
                "Hold180Days": (date - entry_date).days,
            }

        hi = float(bar["High"])
        lo = float(bar["Low"])

        # Conservative ambiguity handling: stop first.
        if lo <= levels["SL"]:
            return {
                "Outcome180": "LOSS",
                "Entry180Date": entry_date,
                "Exit180Date": date,
                "Hold180Days": (date - entry_date).days,
            }

        if hi >= levels["Target"]:
            return {
                "Outcome180": "WIN",
                "Entry180Date": entry_date,
                "Exit180Date": date,
                "Hold180Days": (date - entry_date).days,
            }

    return {
        "Outcome180": "TIMEOUT",
        "Entry180Date": entry_date,
        "Exit180Date": pd.NaT,
        "Hold180Days": np.nan,
    }


def summarize(df):
    r = df[df["Outcome180"].isin(["WIN", "LOSS"])]
    n = len(r)
    wins = int((r["Outcome180"] == "WIN").sum())
    losses = int((r["Outcome180"] == "LOSS").sum())

    return {
        "Resolved": n,
        "Wins": wins,
        "Losses": losses,
        "Timeouts": int((df["Outcome180"] == "TIMEOUT").sum()),
        "Win Rate %": wins / n * 100.0 if n else np.nan,
        "Unique Stocks": int(r["Symbol"].nunique()) if n else 0,
    }


def yearly(df):
    x = df[df["Outcome180"].isin(["WIN", "LOSS"])].copy()
    x["Year"] = pd.to_datetime(x["Entry Date"]).dt.year

    rows = []
    for y, g in x.groupby("Year"):
        s = summarize(g)
        rows.append({"Year": int(y), **s})

    return pd.DataFrame(rows)


def main():
    if not FEATURE_FILE.exists():
        raise SystemExit(
            f"Missing {FEATURE_FILE}. Run pattern_mining_v6.py first."
        )

    data = pd.read_csv(FEATURE_FILE)
    data["Entry Date"] = pd.to_datetime(data["Entry Date"], errors="coerce")

    symbols = sorted(data["Symbol"].dropna().astype(str).unique().tolist())
    market = {}
    failed = []

    total_batches = math.ceil(len(symbols) / BATCH_SIZE)

    for batch_no, start in enumerate(range(0, len(symbols), BATCH_SIZE), 1):
        batch = symbols[start:start+BATCH_SIZE]
        print(f"Target1.80 batch {batch_no}/{total_batches} ({len(batch)} symbols)")

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

    sims = []
    for idx, row in data.iterrows():
        df = market.get(row["Symbol"])
        if df is None:
            continue

        result = simulate_from_next_session(row, df)
        if result is None:
            continue

        sims.append({"_idx": idx, **result})

    sim = pd.DataFrame(sims).set_index("_idx")
    base = data.join(sim, how="inner")

    rows = []

    for name, fn in FILTERS.items():
        selected = base[fn(base).fillna(False)].copy()

        all_stats = summarize(selected)

        split_stats = {}
        for split in ["DEV", "VAL", "TEST"]:
            s = summarize(selected[selected["Split"] == split])
            split_stats[split] = s

        rr = (FIB_TARGET - FIB_ENTRY) / (FIB_ENTRY - FIB_SL)
        wr = all_stats["Win Rate %"] / 100.0 if all_stats["Resolved"] else np.nan
        expectancy_r = wr * rr - (1 - wr) if np.isfinite(wr) else np.nan

        rows.append({
            "Rule": name,
            "Resolved": all_stats["Resolved"],
            "Wins": all_stats["Wins"],
            "Losses": all_stats["Losses"],
            "Win Rate %": all_stats["Win Rate %"],
            "Unique Stocks": all_stats["Unique Stocks"],
            "Reward/Risk": rr,
            "Expectancy R": expectancy_r,
            "DEV Resolved": split_stats["DEV"]["Resolved"],
            "DEV WR %": split_stats["DEV"]["Win Rate %"],
            "VAL Resolved": split_stats["VAL"]["Resolved"],
            "VAL WR %": split_stats["VAL"]["Win Rate %"],
            "TEST Resolved": split_stats["TEST"]["Resolved"],
            "TEST WR %": split_stats["TEST"]["Win Rate %"],
        })

        print("\nRULE:", name)
        print(pd.DataFrame([rows[-1]]).to_string(index=False))
        print("\nYEARLY:")
        print(yearly(selected).to_string(index=False))

    out = pd.DataFrame(rows).sort_values(
        ["Win Rate %", "Resolved"],
        ascending=[False, False],
    )

    out.to_csv(RESULTS / "v8_target180_pattern_summary.csv", index=False)

    print("\n=== V8 TARGET 1.80 SUMMARY ===")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()

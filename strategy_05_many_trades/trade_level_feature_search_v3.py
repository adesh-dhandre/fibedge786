import math
import time
from pathlib import Path
from itertools import combinations

import numpy as np
import pandas as pd
import yfinance as yf

RESULTS = Path("strategy_05_many_trades/results")
TRADES_FILE = RESULTS / "all_base_trades_v1.csv"
OUT_ENRICHED = RESULTS / "all_base_trades_enriched_v3.csv"

BATCH_SIZE = 75
PERIOD = "5y"

# Research split. V2 already inspected 2025-2026 in aggregate, so V3 treats
# these later years as validation/stability checks rather than claiming a
# pristine untouched test.
DEV_END = pd.Timestamp("2024-12-31")

MIN_DEV_RESOLVED = 700
MIN_ALL_RESOLVED = 1000
TOP_SINGLE = 40
TOP_PAIR = 60
TOP_TRIPLE = 120


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
        for c in ["Open", "High", "Low", "Close", "Volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.dropna(subset=["Date", "Open", "High", "Low", "Close"]).reset_index(drop=True)
    except Exception:
        return None


def add_features(df):
    x = df.copy()

    rng = (x["High"] - x["Low"]).replace(0, np.nan)
    prev_close = x["Close"].shift(1)

    tr = pd.concat([
        x["High"] - x["Low"],
        (x["High"] - prev_close).abs(),
        (x["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)

    lower_wick = np.minimum(x["Open"], x["Close"]) - x["Low"]
    body = (x["Close"] - x["Open"]).abs()

    x["Bullish Candle"] = (x["Close"] > x["Open"]).astype(int)
    x["Close Location % V3"] = (x["Close"] - x["Low"]) / rng * 100.0
    x["Lower Wick % V3"] = lower_wick.clip(lower=0) / rng * 100.0
    x["Body % Range"] = body / rng * 100.0

    x["TR3"] = tr.rolling(3, min_periods=3).mean()
    x["TR10"] = tr.rolling(10, min_periods=10).mean()
    x["Compression 3v10"] = x["TR3"] / x["TR10"]

    x["SMA20"] = x["Close"].rolling(20, min_periods=20).mean()
    x["SMA50"] = x["Close"].rolling(50, min_periods=50).mean()
    x["Close vs SMA20 %"] = (x["Close"] / x["SMA20"] - 1.0) * 100.0
    x["SMA20 vs SMA50 %"] = (x["SMA20"] / x["SMA50"] - 1.0) * 100.0

    x["Momentum 5d %"] = x["Close"].pct_change(5) * 100.0
    x["Momentum 10d %"] = x["Close"].pct_change(10) * 100.0
    x["Momentum 20d %"] = x["Close"].pct_change(20) * 100.0

    up = (x["Close"].diff() > 0).astype(float)
    x["Up Close Ratio 5"] = up.rolling(5, min_periods=5).mean()

    x["Range % Close"] = rng / x["Close"] * 100.0

    keep = [
        "Date",
        "Bullish Candle",
        "Close Location % V3",
        "Lower Wick % V3",
        "Body % Range",
        "Compression 3v10",
        "Close vs SMA20 %",
        "SMA20 vs SMA50 %",
        "Momentum 5d %",
        "Momentum 10d %",
        "Momentum 20d %",
        "Up Close Ratio 5",
        "Range % Close",
    ]
    return x[keep].copy()


def enrich_trades(trades):
    symbols = sorted(trades["Symbol"].dropna().astype(str).unique().tolist())
    pieces = []
    failed = []

    total_batches = math.ceil(len(symbols) / BATCH_SIZE)

    for batch_no, start in enumerate(range(0, len(symbols), BATCH_SIZE), 1):
        batch = symbols[start:start + BATCH_SIZE]
        print(f"Feature batch {batch_no}/{total_batches} ({len(batch)} symbols)")

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
                continue
            try:
                f = add_features(df)
                f["Symbol"] = symbol
                pieces.append(f)
            except Exception:
                failed.append(symbol)

        print("  feature symbols:", len(pieces), "| failed:", len(failed))
        time.sleep(0.5)

    if not pieces:
        raise RuntimeError("No feature data produced.")

    features = pd.concat(pieces, ignore_index=True)
    features["Date"] = pd.to_datetime(features["Date"]).dt.normalize()

    t = trades.copy()
    t["Entry Date"] = pd.to_datetime(t["Entry Date"], errors="coerce").dt.normalize()
    t["Recovery / Swing"] = (
        t["Recovery Days"] / t["Swing Days"].replace(0, np.nan)
    )

    enriched = t.merge(
        features,
        left_on=["Symbol", "Entry Date"],
        right_on=["Symbol", "Date"],
        how="left",
    )
    enriched.drop(columns=["Date"], inplace=True, errors="ignore")

    pd.DataFrame({"Symbol": failed}).to_csv(
        RESULTS / "v3_failed_feature_symbols.csv", index=False
    )
    return enriched


def stats(df):
    r = df[df["Outcome"].isin(["WIN", "LOSS"])]
    n = len(r)
    w = int((r["Outcome"] == "WIN").sum())
    return {
        "Resolved": n,
        "Wins": w,
        "Losses": n - w,
        "WR %": (w / n * 100.0) if n else np.nan,
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


def make_conditions():
    conds = []

    def add(name, fn):
        conds.append((name, fn))

    # Existing signal/swing features.
    for v in [8, 10, 12, 15, 18, 20]:
        add(f"Decline>={v}", lambda d, v=v: d["Decline %"] >= v)

    for v in [15, 20, 25, 30, 35, 40]:
        add(f"Swing>={v}", lambda d, v=v: d["Swing Days"] >= v)

    for v in [30, 45, 60, 75, 90, 120]:
        add(f"Recovery<={v}", lambda d, v=v: d["Recovery Days"] <= v)

    for v in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
        add(f"RecoverySwing<={v}", lambda d, v=v: d["Recovery / Swing"] <= v)

    for v in [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        add(f"CloseAbove786>={v}", lambda d, v=v: d["Close Above Entry %"] >= v)

    # New non-volume market structure features.
    add("BullishCandle", lambda d: d["Bullish Candle"] == 1)

    for v in [50, 55, 60, 65, 70, 75, 80]:
        add(f"CloseLocation>={v}", lambda d, v=v: d["Close Location % V3"] >= v)

    for v in [10, 15, 20, 25, 30, 35, 40]:
        add(f"LowerWick<={v}", lambda d, v=v: d["Lower Wick % V3"] <= v)

    for v in [0.70, 0.80, 0.90, 1.00, 1.10]:
        add(f"Compression<={v}", lambda d, v=v: d["Compression 3v10"] <= v)

    for v in [40, 50, 60, 70]:
        add(f"BodyRange>={v}", lambda d, v=v: d["Body % Range"] >= v)

    for v in [0, 2, 4, 6, 8, 10]:
        add(f"CloseVsSMA20>={v}", lambda d, v=v: d["Close vs SMA20 %"] >= v)

    for v in [-5, -2, 0, 2, 5]:
        add(f"SMA20VsSMA50>={v}", lambda d, v=v: d["SMA20 vs SMA50 %"] >= v)

    for v in [0, 2, 4, 6, 8, 10]:
        add(f"Momentum5>={v}", lambda d, v=v: d["Momentum 5d %"] >= v)

    for v in [0, 3, 5, 8, 10, 15]:
        add(f"Momentum10>={v}", lambda d, v=v: d["Momentum 10d %"] >= v)

    for v in [0, 5, 10, 15, 20]:
        add(f"Momentum20>={v}", lambda d, v=v: d["Momentum 20d %"] >= v)

    for v in [0.4, 0.6, 0.8]:
        add(f"UpClose5>={v}", lambda d, v=v: d["Up Close Ratio 5"] >= v)

    return conds


def eval_condition_set(df, condition_set):
    mask = pd.Series(True, index=df.index)
    for _, fn in condition_set:
        mask &= fn(df).fillna(False)
    return df[mask]


def dev_score(s):
    # Reward reliability and volume; do not let tiny high-WR samples dominate.
    if s["Resolved"] <= 0 or pd.isna(s["WR %"]):
        return -1e9
    return s["WR %"] + min(s["Resolved"], 2000) / 2000 * 8.0


def yearly_table(df):
    x = df[df["Outcome"].isin(["WIN", "LOSS"])].copy()
    x["Year"] = pd.to_datetime(x["Entry Date"]).dt.year
    out = []
    for y, g in x.groupby("Year"):
        s = stats(g)
        out.append({"Year": int(y), **s})
    return pd.DataFrame(out)


def main():
    if not TRADES_FILE.exists():
        raise SystemExit(
            f"Missing {TRADES_FILE}. Run V1 first."
        )

    trades = pd.read_csv(TRADES_FILE)

    if OUT_ENRICHED.exists():
        print("Using cached V3 enriched trade file.")
        enriched = pd.read_csv(OUT_ENRICHED)
        enriched["Entry Date"] = pd.to_datetime(enriched["Entry Date"], errors="coerce")
    else:
        print("Building V3 market-structure features...")
        enriched = enrich_trades(trades)
        enriched.to_csv(OUT_ENRICHED, index=False)

    enriched["Entry Date"] = pd.to_datetime(enriched["Entry Date"], errors="coerce")

    feature_cols = [
        "Bullish Candle", "Close Location % V3", "Lower Wick % V3",
        "Body % Range", "Compression 3v10", "Close vs SMA20 %",
        "SMA20 vs SMA50 %", "Momentum 5d %", "Momentum 10d %",
        "Momentum 20d %", "Up Close Ratio 5", "Range % Close",
    ]
    print("Feature coverage:")
    for c in feature_cols:
        print(f"  {c}: {enriched[c].notna().mean()*100:.2f}%")

    dev = enriched[enriched["Entry Date"] <= DEV_END].copy()
    later = enriched[enriched["Entry Date"] > DEV_END].copy()

    conditions = make_conditions()

    # ----- Singles -----
    single_rows = []
    single_sets = []

    for c in conditions:
        z = eval_condition_set(dev, [c])
        s = stats(z)
        if s["Resolved"] < MIN_DEV_RESOLVED:
            continue
        single_rows.append({
            "Rule": c[0],
            **s,
            "Wilson Low %": wilson_lower(s["Wins"], s["Resolved"]),
            "Score": dev_score(s),
        })
        single_sets.append(([c], s))

    single_sets.sort(key=lambda x: dev_score(x[1]), reverse=True)
    best_singles = [x[0] for x in single_sets[:TOP_SINGLE]]

    # ----- Pairs -----
    pair_candidates = {}
    for a, b in combinations(best_singles, 2):
        names = tuple(sorted([a[0][0], b[0][0]]))
        cond_set = [a[0], b[0]]
        z = eval_condition_set(dev, cond_set)
        s = stats(z)
        if s["Resolved"] < MIN_DEV_RESOLVED:
            continue
        pair_candidates[names] = (cond_set, s)

    pair_ranked = sorted(
        pair_candidates.values(),
        key=lambda x: dev_score(x[1]),
        reverse=True,
    )[:TOP_PAIR]

    # ----- Triples -----
    triple_candidates = {}
    for pair_set, _ in pair_ranked:
        pair_names = {c[0] for c in pair_set}
        for c in conditions:
            if c[0] in pair_names:
                continue
            names = tuple(sorted(list(pair_names) + [c[0]]))
            cond_set = pair_set + [c]
            z = eval_condition_set(dev, cond_set)
            s = stats(z)
            if s["Resolved"] < MIN_DEV_RESOLVED:
                continue
            triple_candidates[names] = (cond_set, s)

    triple_ranked = sorted(
        triple_candidates.values(),
        key=lambda x: dev_score(x[1]),
        reverse=True,
    )[:TOP_TRIPLE]

    # Evaluate retained candidates on later years and full history.
    candidate_sets = best_singles + [x[0] for x in pair_ranked] + [x[0] for x in triple_ranked]

    rows = []
    seen = set()
    for cond_set in candidate_sets:
        key = tuple(sorted(c[0] for c in cond_set))
        if key in seen:
            continue
        seen.add(key)

        dev_sel = eval_condition_set(dev, cond_set)
        later_sel = eval_condition_set(later, cond_set)
        all_sel = eval_condition_set(enriched, cond_set)

        sd = stats(dev_sel)
        sl = stats(later_sel)
        sa = stats(all_sel)

        rows.append({
            "Rule": " AND ".join(key),
            "Conditions": len(key),
            "Dev Resolved": sd["Resolved"],
            "Dev WR %": sd["WR %"],
            "Later Resolved": sl["Resolved"],
            "Later WR %": sl["WR %"],
            "All Resolved": sa["Resolved"],
            "All WR %": sa["WR %"],
            "Unique Stocks": sa["Unique Stocks"],
            "Later Wilson Low %": wilson_lower(sl["Wins"], sl["Resolved"]),
        })

    result = pd.DataFrame(rows)
    result.to_csv(RESULTS / "v3_candidate_rules.csv", index=False)

    hv = result[result["All Resolved"] >= MIN_ALL_RESOLVED].sort_values(
        ["Later WR %", "All Resolved"],
        ascending=[False, False],
    )
    hv.to_csv(RESULTS / "v3_high_volume_frontier.csv", index=False)

    target = hv[hv["Later WR %"] >= 70.0].copy()
    target.to_csv(RESULTS / "v3_target_hits.csv", index=False)

    best_any = result.sort_values(
        ["Later WR %", "All Resolved"],
        ascending=[False, False],
    )

    print("\n=== V3 TARGET: LATER WR >=70% AND ALL RESOLVED >=1000 ===")
    if target.empty:
        print("NONE")
    else:
        print(target.head(25).to_string(index=False))

    print("\n=== V3 HIGH-VOLUME FRONTIER ===")
    if hv.empty:
        print("NONE")
    else:
        print(hv.head(30).to_string(index=False))

    print("\n=== V3 BEST LATER-PERIOD RULES ===")
    print(best_any.head(30).to_string(index=False))

    # Year-by-year detail for best 5 high-volume rules.
    if not hv.empty:
        print("\n=== YEARLY STABILITY: TOP 5 HIGH-VOLUME RULES ===")
        for _, row in hv.head(5).iterrows():
            names = row["Rule"].split(" AND ")
            cond_set = [c for c in conditions if c[0] in names]
            selected = eval_condition_set(enriched, cond_set)
            print("\nRULE:", row["Rule"])
            print(yearly_table(selected).to_string(index=False))


if __name__ == "__main__":
    main()

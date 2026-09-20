import hashlib
import math
import time
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

# ============================================================
# STRATEGY 05 V6 — 0.786 -> 1.260 PATTERN MINER
# Research only. No production files are touched.
#
# Goal:
#   Find repeatable candle / momentum / trend / volatility /
#   volume patterns associated with successful moves from
#   Fib 0.786 to Fib 1.260, while avoiding tiny-sample overfit.
#
# IMPORTANT:
#   MODE A (PRE_TOUCH) uses ONLY information known before the
#   0.786 touch day. This is the cleanest mode for an entry at
#   the 0.786 touch.
#
#   MODE B (EOD_CONFIRM) may use the touch day's completed
#   candle, so it is evaluated from the NEXT trading session.
#   This avoids using the completed candle to "predict" an
#   outcome that already happened intraday on that same candle.
# ============================================================

RESULTS = Path("strategy_05_many_trades/results")
RESULTS.mkdir(parents=True, exist_ok=True)

BASE_TRADES_FILE = RESULTS / "all_base_trades_v1.csv"
FEATURE_CACHE = RESULTS / "pattern_features_v6.csv"

PERIOD = "5y"
BATCH_SIZE = 75
MAX_HOLD_CALENDAR_DAYS = 60

FIB_ENTRY = 0.786
FIB_SL = 0.500
FIB_TARGET = 1.260

# Minimum sample sizes for serious candidates.
MIN_DEV_RESOLVED = 700
MIN_ALL_RESOLVED = 1000
TARGET_WR = 70.0

# Beam sizes keep the search broad without brute-force explosion.
TOP_SINGLES = 70
TOP_PAIRS = 100
TOP_TRIPLES = 150

# Deterministic stock holdout. Rules are mined only on DEV symbols.
# This is useful because calendar years have already been inspected
# in earlier V2-V5 experiments.
DEV_BUCKET_MAX = 69       # 70%
VAL_BUCKET_MAX = 84       # next 15%
# TEST = remaining 15%


def symbol_bucket(symbol):
    h = hashlib.sha256(str(symbol).encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 100


def split_name(symbol):
    b = symbol_bucket(symbol)
    if b <= DEV_BUCKET_MAX:
        return "DEV"
    if b <= VAL_BUCKET_MAX:
        return "VAL"
    return "TEST"


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
        df["Date"] = pd.to_datetime(
            df["Date"], errors="coerce"
        ).dt.tz_localize(None)

        for c in ["Open", "High", "Low", "Close", "Volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        required = ["Date", "Open", "High", "Low", "Close"]
        return (
            df.dropna(subset=required)
            .sort_values("Date")
            .reset_index(drop=True)
        )
    except Exception:
        return None


def reconstruct_levels(row):
    entry = float(row["Entry"])
    sl = float(row["SL"])
    price_range = (entry - sl) / (FIB_ENTRY - FIB_SL)

    if not np.isfinite(price_range) or price_range <= 0:
        return None

    low = sl - price_range * FIB_SL
    high = low + price_range
    target = low + price_range * FIB_TARGET

    return {
        "Swing High": high,
        "Swing Low": low,
        "Fib Entry": entry,
        "Fib SL": sl,
        "Fib Target": target,
        "Swing Range": price_range,
    }


def rolling_rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.rolling(period, min_periods=period).mean()
    avg_loss = loss.rolling(period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def add_daily_features(df):
    x = df.copy()

    prev_close = x["Close"].shift(1)
    rng = (x["High"] - x["Low"]).replace(0, np.nan)
    body_signed = x["Close"] - x["Open"]
    body = body_signed.abs()
    lower_wick = np.minimum(x["Open"], x["Close"]) - x["Low"]
    upper_wick = x["High"] - np.maximum(x["Open"], x["Close"])

    tr = pd.concat([
        x["High"] - x["Low"],
        (x["High"] - prev_close).abs(),
        (x["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)

    x["Bull"] = (x["Close"] > x["Open"]).astype(int)
    x["Bear"] = (x["Close"] < x["Open"]).astype(int)
    x["BodyPct"] = body / rng * 100.0
    x["BodySignedPct"] = body_signed / rng * 100.0
    x["CloseLocPct"] = (x["Close"] - x["Low"]) / rng * 100.0
    x["LowerWickPct"] = lower_wick.clip(lower=0) / rng * 100.0
    x["UpperWickPct"] = upper_wick.clip(lower=0) / rng * 100.0
    x["RangePctClose"] = rng / x["Close"] * 100.0

    # Close-to-close / gap momentum.
    x["Ret1Pct"] = x["Close"].pct_change(1) * 100.0
    x["Ret3Pct"] = x["Close"].pct_change(3) * 100.0
    x["Ret5Pct"] = x["Close"].pct_change(5) * 100.0
    x["Ret10Pct"] = x["Close"].pct_change(10) * 100.0
    x["Ret20Pct"] = x["Close"].pct_change(20) * 100.0
    x["GapPct"] = (x["Open"] / prev_close - 1.0) * 100.0

    up = (x["Close"].diff() > 0).astype(float)
    x["UpRatio3"] = up.rolling(3, min_periods=3).mean()
    x["UpRatio5"] = up.rolling(5, min_periods=5).mean()
    x["UpRatio8"] = up.rolling(8, min_periods=8).mean()

    # Trend structure.
    x["SMA10"] = x["Close"].rolling(10, min_periods=10).mean()
    x["SMA20"] = x["Close"].rolling(20, min_periods=20).mean()
    x["SMA50"] = x["Close"].rolling(50, min_periods=50).mean()
    x["CloseVsSMA10Pct"] = (x["Close"] / x["SMA10"] - 1.0) * 100.0
    x["CloseVsSMA20Pct"] = (x["Close"] / x["SMA20"] - 1.0) * 100.0
    x["SMA10Vs20Pct"] = (x["SMA10"] / x["SMA20"] - 1.0) * 100.0
    x["SMA20Vs50Pct"] = (x["SMA20"] / x["SMA50"] - 1.0) * 100.0
    x["RSI14"] = rolling_rsi(x["Close"], 14)

    # Volatility / compression.
    x["ATR3"] = tr.rolling(3, min_periods=3).mean()
    x["ATR5"] = tr.rolling(5, min_periods=5).mean()
    x["ATR10"] = tr.rolling(10, min_periods=10).mean()
    x["ATR20"] = tr.rolling(20, min_periods=20).mean()
    x["ATR3v10"] = x["ATR3"] / x["ATR10"]
    x["ATR5v20"] = x["ATR5"] / x["ATR20"]

    # Breakout / higher-high / higher-low structure.
    for n in [2, 3, 5, 10, 20]:
        x[f"PrevHigh{n}"] = x["High"].shift(1).rolling(n, min_periods=n).max()
        x[f"PrevLow{n}"] = x["Low"].shift(1).rolling(n, min_periods=n).min()
        x[f"CloseBreakHigh{n}Pct"] = (
            x["Close"] / x[f"PrevHigh{n}"] - 1.0
        ) * 100.0

    higher_high = (x["High"].diff() > 0).astype(float)
    higher_low = (x["Low"].diff() > 0).astype(float)
    for n in [3, 5]:
        x[f"HigherHighRatio{n}"] = higher_high.rolling(n, min_periods=n).mean()
        x[f"HigherLowRatio{n}"] = higher_low.rolling(n, min_periods=n).mean()

    # Volume features. These are optional candidates, not required by the strategy.
    if "Volume" in x.columns:
        vol20 = x["Volume"].rolling(20, min_periods=20).mean()
        x["RVOL20"] = x["Volume"] / vol20
        x["VolumeUp3"] = (
            (x["Volume"].diff() > 0).astype(float)
            .rolling(3, min_periods=3)
            .mean()
        )
    else:
        x["RVOL20"] = np.nan
        x["VolumeUp3"] = np.nan

    # Named candle-pattern approximations (objective definitions).
    prev_open = x["Open"].shift(1)
    prev_close2 = x["Close"].shift(1)
    prev_body_low = np.minimum(prev_open, prev_close2)
    prev_body_high = np.maximum(prev_open, prev_close2)
    cur_body_low = np.minimum(x["Open"], x["Close"])
    cur_body_high = np.maximum(x["Open"], x["Close"])

    x["BullEngulf"] = (
        (x["Bull"] == 1)
        & (prev_close2 < prev_open)
        & (cur_body_low <= prev_body_low)
        & (cur_body_high >= prev_body_high)
    ).astype(int)

    x["HammerLike"] = (
        (lower_wick >= body * 2.0)
        & (upper_wick <= body * 1.0)
        & (x["CloseLocPct"] >= 60)
    ).astype(int)

    x["MarubozuLike"] = (
        (x["BodyPct"] >= 70)
        & (x["CloseLocPct"] >= 80)
        & (x["Bull"] == 1)
    ).astype(int)

    x["InsideBar"] = (
        (x["High"] < x["High"].shift(1))
        & (x["Low"] > x["Low"].shift(1))
    ).astype(int)

    x["OutsideBull"] = (
        (x["High"] > x["High"].shift(1))
        & (x["Low"] < x["Low"].shift(1))
        & (x["Bull"] == 1)
    ).astype(int)

    # 3 bullish candles with progressively higher closes.
    x["ThreeUpCloses"] = (
        (x["Close"] > x["Close"].shift(1))
        & (x["Close"].shift(1) > x["Close"].shift(2))
        & (x["Close"].shift(2) > x["Close"].shift(3))
    ).astype(int)

    # Narrow-range compression before breakout.
    for n in [3, 5, 7]:
        rolling_min_range = rng.rolling(n, min_periods=n).min()
        x[f"NR{n}"] = (rng <= rolling_min_range + 1e-12).astype(int)

    return x


def row_feature_snapshot(feature_df, idx):
    if idx < 0 or idx >= len(feature_df):
        return {}

    r = feature_df.iloc[idx]

    names = [
        "Bull", "Bear", "BodyPct", "BodySignedPct", "CloseLocPct",
        "LowerWickPct", "UpperWickPct", "RangePctClose",
        "Ret1Pct", "Ret3Pct", "Ret5Pct", "Ret10Pct", "Ret20Pct", "GapPct",
        "UpRatio3", "UpRatio5", "UpRatio8",
        "CloseVsSMA10Pct", "CloseVsSMA20Pct", "SMA10Vs20Pct",
        "SMA20Vs50Pct", "RSI14", "ATR3v10", "ATR5v20",
        "CloseBreakHigh2Pct", "CloseBreakHigh3Pct", "CloseBreakHigh5Pct",
        "CloseBreakHigh10Pct", "CloseBreakHigh20Pct",
        "HigherHighRatio3", "HigherHighRatio5",
        "HigherLowRatio3", "HigherLowRatio5",
        "RVOL20", "VolumeUp3",
        "BullEngulf", "HammerLike", "MarubozuLike", "InsideBar",
        "OutsideBull", "ThreeUpCloses", "NR3", "NR5", "NR7",
    ]

    return {k: r.get(k, np.nan) for k in names}


def simulate_eod_confirm(row, raw_df, signal_idx):
    levels = reconstruct_levels(row)
    if levels is None:
        return None

    sl = levels["Fib SL"]
    target = levels["Fib Target"]

    # Confirmation is known only after signal candle closes.
    # Start evaluation from the NEXT trading candle.
    start_idx = signal_idx + 1
    if start_idx >= len(raw_df):
        return None

    entry_date = pd.Timestamp(raw_df.loc[start_idx, "Date"]).normalize()

    for j in range(start_idx, len(raw_df)):
        bar = raw_df.loc[j]
        date = pd.Timestamp(bar["Date"]).normalize()

        if (date - entry_date).days > MAX_HOLD_CALENDAR_DAYS:
            return {
                "EOD Outcome": "TIMEOUT",
                "EOD Entry Date": entry_date,
                "EOD Exit Date": date,
                "EOD Hold Days": (date - entry_date).days,
            }

        hi = float(bar["High"])
        lo = float(bar["Low"])

        # Conservative same-day ambiguity: SL first.
        if lo <= sl:
            return {
                "EOD Outcome": "LOSS",
                "EOD Entry Date": entry_date,
                "EOD Exit Date": date,
                "EOD Hold Days": (date - entry_date).days,
            }

        if hi >= target:
            return {
                "EOD Outcome": "WIN",
                "EOD Entry Date": entry_date,
                "EOD Exit Date": date,
                "EOD Hold Days": (date - entry_date).days,
            }

    return {
        "EOD Outcome": "TIMEOUT",
        "EOD Entry Date": entry_date,
        "EOD Exit Date": pd.NaT,
        "EOD Hold Days": np.nan,
    }


def build_pattern_dataset(trades):
    symbols = sorted(trades["Symbol"].dropna().astype(str).unique().tolist())
    market = {}
    features = {}
    failed = []

    total_batches = math.ceil(len(symbols) / BATCH_SIZE)

    for batch_no, start in enumerate(range(0, len(symbols), BATCH_SIZE), 1):
        batch = symbols[start:start+BATCH_SIZE]
        print(f"Pattern batch {batch_no}/{total_batches} ({len(batch)} symbols)")

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
                market[symbol] = df
                features[symbol] = add_daily_features(df)
            except Exception:
                failed.append(symbol)

        print("  loaded:", len(market), "| failed:", len(failed))
        time.sleep(0.5)

    out = []

    for k, (_, tr) in enumerate(trades.iterrows(), 1):
        symbol = tr["Symbol"]
        raw = market.get(symbol)
        feat = features.get(symbol)
        if raw is None or feat is None:
            continue

        signal_date = pd.Timestamp(tr["Entry Date"]).normalize()
        matches = raw.index[raw["Date"].dt.normalize() == signal_date].tolist()
        if not matches:
            continue

        signal_idx = int(matches[0])
        levels = reconstruct_levels(tr)
        if levels is None:
            continue

        record = tr.to_dict()
        record["Split"] = split_name(symbol)

        # PRE_TOUCH: ONLY previous completed candle and historical context.
        pre = row_feature_snapshot(feat, signal_idx - 1)
        for name, value in pre.items():
            record[f"PRE_{name}"] = value

        # Additional multi-candle pattern context before touch.
        if signal_idx >= 2:
            record["PRE2_Bull"] = feat.loc[signal_idx - 2, "Bull"]
            record["PRE2_CloseLocPct"] = feat.loc[signal_idx - 2, "CloseLocPct"]
            record["PRE2_BodyPct"] = feat.loc[signal_idx - 2, "BodyPct"]
        else:
            record["PRE2_Bull"] = np.nan
            record["PRE2_CloseLocPct"] = np.nan
            record["PRE2_BodyPct"] = np.nan

        # EOD_CONFIRM: touch-day completed candle, allowed only for
        # next-session outcome simulation.
        sig = row_feature_snapshot(feat, signal_idx)
        for name, value in sig.items():
            record[f"SIG_{name}"] = value

        sig_close = float(raw.loc[signal_idx, "Close"])
        record["SIG_CloseAbove786Pct"] = (
            sig_close / levels["Fib Entry"] - 1.0
        ) * 100.0

        eod = simulate_eod_confirm(tr, raw, signal_idx)
        if eod is not None:
            record.update(eod)
        else:
            record["EOD Outcome"] = np.nan
            record["EOD Entry Date"] = pd.NaT
            record["EOD Exit Date"] = pd.NaT
            record["EOD Hold Days"] = np.nan

        out.append(record)

        if k % 2500 == 0:
            print("  mapped trades:", k)

    pd.DataFrame({"Symbol": failed}).to_csv(
        RESULTS / "pattern_v6_failed_symbols.csv", index=False
    )

    result = pd.DataFrame(out)
    result.to_csv(FEATURE_CACHE, index=False)
    return result


def stats(df, outcome_col):
    r = df[df[outcome_col].isin(["WIN", "LOSS"])]
    n = len(r)
    wins = int((r[outcome_col] == "WIN").sum())
    return {
        "Resolved": n,
        "Wins": wins,
        "Losses": n - wins,
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


def condition_library(prefix):
    C = []

    def add(name, col, op, value):
        C.append((name, col, op, value))

    # Candle direction / body / wick / location.
    add("Bull", f"{prefix}_Bull", ">=", 1)
    for v in [50, 60, 70, 80]:
        add(f"Body>={v}", f"{prefix}_BodyPct", ">=", v)
    for v in [55, 60, 65, 70, 75, 80, 85, 90]:
        add(f"CloseLoc>={v}", f"{prefix}_CloseLocPct", ">=", v)
    for v in [5, 10, 15, 20, 25, 30]:
        add(f"LowerWick<={v}", f"{prefix}_LowerWickPct", "<=", v)
    for v in [5, 10, 15, 20, 25, 30]:
        add(f"UpperWick<={v}", f"{prefix}_UpperWickPct", "<=", v)

    # Momentum.
    for col, vals in [
        ("Ret1Pct", [0, 1, 2, 3, 4, 5]),
        ("Ret3Pct", [0, 2, 4, 6, 8, 10, 12]),
        ("Ret5Pct", [0, 3, 5, 8, 10, 12, 15]),
        ("Ret10Pct", [0, 5, 8, 10, 15, 20]),
        ("Ret20Pct", [0, 5, 10, 15, 20, 30]),
    ]:
        for v in vals:
            add(f"{col}>={v}", f"{prefix}_{col}", ">=", v)

    for col, vals in [
        ("UpRatio3", [0.67, 1.0]),
        ("UpRatio5", [0.6, 0.8, 1.0]),
        ("UpRatio8", [0.625, 0.75, 0.875]),
    ]:
        for v in vals:
            add(f"{col}>={v}", f"{prefix}_{col}", ">=", v)

    # Trend / RSI.
    for v in [0, 2, 4, 6, 8, 10]:
        add(f"CloseVsSMA10>={v}", f"{prefix}_CloseVsSMA10Pct", ">=", v)
        add(f"CloseVsSMA20>={v}", f"{prefix}_CloseVsSMA20Pct", ">=", v)

    for v in [-5, -2, 0, 2, 5, 8]:
        add(f"SMA10Vs20>={v}", f"{prefix}_SMA10Vs20Pct", ">=", v)
        add(f"SMA20Vs50>={v}", f"{prefix}_SMA20Vs50Pct", ">=", v)

    for v in [45, 50, 55, 60, 65, 70]:
        add(f"RSI14>={v}", f"{prefix}_RSI14", ">=", v)
    for v in [70, 75, 80]:
        add(f"RSI14<={v}", f"{prefix}_RSI14", "<=", v)

    # Compression / expansion.
    for v in [0.70, 0.80, 0.90, 1.00, 1.10]:
        add(f"ATR3v10<={v}", f"{prefix}_ATR3v10", "<=", v)
        add(f"ATR5v20<={v}", f"{prefix}_ATR5v20", "<=", v)
    for v in [1.0, 1.1, 1.2, 1.3]:
        add(f"ATR3v10>={v}", f"{prefix}_ATR3v10", ">=", v)

    # Breakout.
    for n in [2, 3, 5, 10, 20]:
        for v in [0, 1, 2]:
            add(
                f"BreakHigh{n}>={v}",
                f"{prefix}_CloseBreakHigh{n}Pct",
                ">=",
                v,
            )

    for col in [
        "HigherHighRatio3", "HigherHighRatio5",
        "HigherLowRatio3", "HigherLowRatio5",
    ]:
        for v in [0.6, 0.8, 1.0]:
            add(f"{col}>={v}", f"{prefix}_{col}", ">=", v)

    # Volume.
    for v in [1.0, 1.2, 1.5, 2.0]:
        add(f"RVOL20>={v}", f"{prefix}_RVOL20", ">=", v)
    for v in [0.67, 1.0]:
        add(f"VolumeUp3>={v}", f"{prefix}_VolumeUp3", ">=", v)

    # Named patterns.
    for col in [
        "BullEngulf", "HammerLike", "MarubozuLike", "InsideBar",
        "OutsideBull", "ThreeUpCloses", "NR3", "NR5", "NR7",
    ]:
        add(col, f"{prefix}_{col}", ">=", 1)

    return C


def apply_condition(df, cond):
    _, col, op, value = cond
    s = df[col]

    if op == ">=":
        return s >= value
    if op == "<=":
        return s <= value

    raise ValueError(op)


def apply_set(df, conds):
    mask = pd.Series(True, index=df.index)
    for c in conds:
        mask &= apply_condition(df, c).fillna(False)
    return df[mask]


def dev_score(s):
    if s["Resolved"] <= 0 or pd.isna(s["WR %"]):
        return -1e9

    # Strongly reward win rate but also reward sample size.
    volume_bonus = min(s["Resolved"], 2500) / 2500.0 * 10.0
    return s["WR %"] + volume_bonus


def dedupe_conditions(cond_set):
    # No exact duplicate column/operator/value combinations.
    seen = set()
    out = []
    for c in cond_set:
        key = (c[1], c[2], c[3])
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def mine_mode(data, mode_name, outcome_col, prefix):
    print(f"\n{'='*90}")
    print("MINING MODE:", mode_name)
    print("="*90)

    dev = data[data["Split"] == "DEV"].copy()
    val = data[data["Split"] == "VAL"].copy()
    test = data[data["Split"] == "TEST"].copy()

    conds = condition_library(prefix)

    if mode_name == "EOD_CONFIRM":
        # Fib-specific post-touch close confirmation thresholds.
        for v in [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
            conds.append((
                f"CloseAbove786>={v}",
                "SIG_CloseAbove786Pct",
                ">=",
                v,
            ))

    # ---------------- singles ----------------
    singles = []
    for c in conds:
        z = apply_set(dev, [c])
        s = stats(z, outcome_col)
        if s["Resolved"] >= MIN_DEV_RESOLVED:
            singles.append(([c], s))

    singles.sort(key=lambda x: dev_score(x[1]), reverse=True)
    top_single_sets = [x[0] for x in singles[:TOP_SINGLES]]

    # ---------------- pairs ----------------
    pair_map = {}
    for a, b in combinations(top_single_sets, 2):
        cs = dedupe_conditions(a + b)
        key = tuple(sorted(c[0] for c in cs))
        if key in pair_map:
            continue

        z = apply_set(dev, cs)
        s = stats(z, outcome_col)

        if s["Resolved"] >= MIN_DEV_RESOLVED:
            pair_map[key] = (cs, s)

    pair_ranked = sorted(
        pair_map.values(),
        key=lambda x: dev_score(x[1]),
        reverse=True,
    )[:TOP_PAIRS]

    # ---------------- triples ----------------
    triple_map = {}
    for pair_set, _ in pair_ranked:
        pair_names = {c[0] for c in pair_set}

        for c in conds:
            if c[0] in pair_names:
                continue

            cs = dedupe_conditions(pair_set + [c])
            key = tuple(sorted(x[0] for x in cs))
            if key in triple_map:
                continue

            z = apply_set(dev, cs)
            s = stats(z, outcome_col)

            if s["Resolved"] >= MIN_DEV_RESOLVED:
                triple_map[key] = (cs, s)

    triple_ranked = sorted(
        triple_map.values(),
        key=lambda x: dev_score(x[1]),
        reverse=True,
    )[:TOP_TRIPLES]

    candidate_sets = (
        top_single_sets
        + [x[0] for x in pair_ranked]
        + [x[0] for x in triple_ranked]
    )

    rows = []
    seen = set()

    for cs in candidate_sets:
        key = tuple(sorted(c[0] for c in cs))
        if key in seen:
            continue
        seen.add(key)

        d = stats(apply_set(dev, cs), outcome_col)
        v = stats(apply_set(val, cs), outcome_col)
        t = stats(apply_set(test, cs), outcome_col)
        a = stats(apply_set(data, cs), outcome_col)

        rows.append({
            "Mode": mode_name,
            "Rule": " AND ".join(key),
            "Conditions": len(key),
            "Dev Resolved": d["Resolved"],
            "Dev WR %": d["WR %"],
            "Val Resolved": v["Resolved"],
            "Val WR %": v["WR %"],
            "Test Resolved": t["Resolved"],
            "Test WR %": t["WR %"],
            "All Resolved": a["Resolved"],
            "All WR %": a["WR %"],
            "Unique Stocks": a["Unique Stocks"],
            "Test Wilson Low %": wilson_lower(t["Wins"], t["Resolved"]),
        })

    out = pd.DataFrame(rows)

    # Serious high-volume candidates.
    high_volume = out[out["All Resolved"] >= MIN_ALL_RESOLVED].copy()

    # Rank by the weakest of DEV/VAL/TEST to prefer stable rules.
    if not high_volume.empty:
        high_volume["Worst Split WR %"] = high_volume[
            ["Dev WR %", "Val WR %", "Test WR %"]
        ].min(axis=1)

        high_volume = high_volume.sort_values(
            ["Worst Split WR %", "All WR %", "All Resolved"],
            ascending=[False, False, False],
        )

    target = high_volume[
        (high_volume["Dev WR %"] >= TARGET_WR)
        & (high_volume["Val WR %"] >= TARGET_WR)
        & (high_volume["Test WR %"] >= TARGET_WR)
    ].copy() if not high_volume.empty else high_volume.copy()

    out.to_csv(
        RESULTS / f"v6_{mode_name.lower()}_all_candidates.csv",
        index=False,
    )
    high_volume.to_csv(
        RESULTS / f"v6_{mode_name.lower()}_high_volume.csv",
        index=False,
    )
    target.to_csv(
        RESULTS / f"v6_{mode_name.lower()}_70plus_all_splits.csv",
        index=False,
    )

    print("\n--- 70%+ ON DEV + VAL + TEST AND 1000+ ALL RESOLVED ---")
    if target.empty:
        print("NONE")
    else:
        print(target.head(30).to_string(index=False))

    print("\n--- HIGH-VOLUME STABILITY FRONTIER ---")
    if high_volume.empty:
        print("NONE")
    else:
        print(high_volume.head(40).to_string(index=False))

    return out, high_volume, target


def yearly_breakdown(data, rule_row, mode_name, outcome_col, prefix):
    conds = condition_library(prefix)

    if mode_name == "EOD_CONFIRM":
        for v in [0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
            conds.append((
                f"CloseAbove786>={v}",
                "SIG_CloseAbove786Pct",
                ">=",
                v,
            ))

    lookup = {c[0]: c for c in conds}
    names = rule_row["Rule"].split(" AND ")
    cs = [lookup[n] for n in names if n in lookup]

    selected = apply_set(data, cs).copy()
    selected["Year"] = pd.to_datetime(selected["Entry Date"]).dt.year

    rows = []
    for year, g in selected.groupby("Year"):
        s = stats(g, outcome_col)
        rows.append({"Year": int(year), **s})

    return pd.DataFrame(rows)


def main():
    if not BASE_TRADES_FILE.exists():
        raise SystemExit(
            f"Missing {BASE_TRADES_FILE}. Run trade_level_search_v1.py first."
        )

    if FEATURE_CACHE.exists():
        print("Using cached V6 pattern dataset:", FEATURE_CACHE)
        data = pd.read_csv(FEATURE_CACHE)
    else:
        print("Building V6 pattern dataset...")
        trades = pd.read_csv(BASE_TRADES_FILE)
        data = build_pattern_dataset(trades)

    data["Entry Date"] = pd.to_datetime(data["Entry Date"], errors="coerce")

    print("\nDataset rows:", len(data))
    print("Split distribution:")
    print(data["Split"].value_counts().to_string())

    print("\nOriginal touch-entry baseline:")
    print(stats(data, "Outcome"))

    print("\nEOD-confirm next-session baseline:")
    print(stats(data, "EOD Outcome"))

    pre_all, pre_hv, pre_target = mine_mode(
        data,
        mode_name="PRE_TOUCH",
        outcome_col="Outcome",
        prefix="PRE",
    )

    eod_all, eod_hv, eod_target = mine_mode(
        data,
        mode_name="EOD_CONFIRM",
        outcome_col="EOD Outcome",
        prefix="SIG",
    )

    combined = pd.concat(
        [
            pre_hv.assign(OutcomeMode="Touch at 0.786"),
            eod_hv.assign(OutcomeMode="Confirm EOD -> next session"),
        ],
        ignore_index=True,
    )

    if not combined.empty:
        combined = combined.sort_values(
            ["Worst Split WR %", "All WR %", "All Resolved"],
            ascending=[False, False, False],
        )
        combined.to_csv(
            RESULTS / "v6_combined_high_volume_frontier.csv",
            index=False,
        )

        print("\n" + "="*90)
        print("V6 COMBINED HIGH-VOLUME FRONTIER")
        print("="*90)
        print(combined.head(50).to_string(index=False))

    # Year-by-year stability for the best high-volume rule from each mode.
    for mode_name, hv, outcome_col, prefix in [
        ("PRE_TOUCH", pre_hv, "Outcome", "PRE"),
        ("EOD_CONFIRM", eod_hv, "EOD Outcome", "SIG"),
    ]:
        if hv.empty:
            continue

        print("\n" + "="*90)
        print("YEARLY STABILITY:", mode_name)
        print("="*90)

        for _, row in hv.head(5).iterrows():
            print("\nRULE:", row["Rule"])
            print(
                yearly_breakdown(
                    data, row, mode_name, outcome_col, prefix
                ).to_string(index=False)
            )


if __name__ == "__main__":
    main()

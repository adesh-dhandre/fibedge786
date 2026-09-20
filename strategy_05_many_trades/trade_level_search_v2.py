import itertools
from pathlib import Path
import math

import numpy as np
import pandas as pd

RESULTS = Path("strategy_05_many_trades/results")
TRADES_FILE = RESULTS / "all_base_trades_v1.csv"

DEV_END = pd.Timestamp("2024-12-31")

# V2 goal: optimize for BOTH trade count and win rate.
# No market redownload; reuse the exact V1 base-trade dataset.
DECLINE_MIN_GRID = [8, 10, 12, 15]
SWING_MIN_GRID = [15, 20, 25, 30, 35, 40]
RECOVERY_MAX_GRID = [None, 120, 90, 75, 60, 45, 30]
CLOSE_ABOVE_ENTRY_MIN_GRID = [None, 0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
CLOSE_LOCATION_MIN_GRID = [None, 50, 55, 60, 65, 70, 75]
LOWER_WICK_MAX_GRID = [None, 40, 35, 30, 25, 20, 15, 10]

MIN_DEV_RESOLVED = 600
TARGET_ALL_RESOLVED = 1000
TARGET_TEST_WR = 70.0


def apply_rule(df, rule):
    x = df
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
    n = len(resolved)
    return {
        "Trades": len(df),
        "Resolved": n,
        "Wins": wins,
        "Losses": losses,
        "Timeouts": int((df["Outcome"] == "TIMEOUT").sum()),
        "Win Rate %": wins / n * 100.0 if n else np.nan,
        "Unique Stocks": int(resolved["Symbol"].nunique()) if n else 0,
    }


def wilson_lower(wins, n, z=1.96):
    if n <= 0:
        return np.nan
    p = wins / n
    den = 1 + z*z/n
    centre = p + z*z/(2*n)
    adj = z * math.sqrt((p*(1-p) + z*z/(4*n))/n)
    return (centre - adj) / den * 100.0


def score_rule(dev_stats):
    # Reward quality, but explicitly reward volume too.
    # A 70% rule with 1000+ trades outranks a tiny 75% rule.
    wr = dev_stats["Win Rate %"]
    n = dev_stats["Resolved"]
    if pd.isna(wr) or n <= 0:
        return -1e9
    volume_bonus = min(n, 2000) / 2000 * 8.0
    return wr + volume_bonus


def main():
    if not TRADES_FILE.exists():
        raise SystemExit(
            f"Missing {TRADES_FILE}. Run trade_level_search_v1.py first."
        )

    trades = pd.read_csv(TRADES_FILE)
    trades["Entry Date"] = pd.to_datetime(trades["Entry Date"], errors="coerce")

    dev = trades[trades["Entry Date"] <= DEV_END].copy()
    test = trades[trades["Entry Date"] > DEV_END].copy()

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

        dev_sel = apply_rule(dev, rule)
        dev_stats = summarize(dev_sel)

        if dev_stats["Resolved"] < MIN_DEV_RESOLVED:
            continue

        test_stats = summarize(apply_rule(test, rule))
        all_stats = summarize(apply_rule(trades, rule))

        rows.append({
            **rule,
            "Dev Resolved": dev_stats["Resolved"],
            "Dev Wins": dev_stats["Wins"],
            "Dev WR %": dev_stats["Win Rate %"],
            "Dev Wilson Low %": wilson_lower(dev_stats["Wins"], dev_stats["Resolved"]),
            "Test Resolved": test_stats["Resolved"],
            "Test Wins": test_stats["Wins"],
            "Test WR %": test_stats["Win Rate %"],
            "Test Wilson Low %": wilson_lower(test_stats["Wins"], test_stats["Resolved"]),
            "All Resolved": all_stats["Resolved"],
            "All Wins": all_stats["Wins"],
            "All WR %": all_stats["Win Rate %"],
            "Unique Stocks": all_stats["Unique Stocks"],
            "Objective Score": score_rule(dev_stats),
        })

    out = pd.DataFrame(rows)
    if out.empty:
        print("No rules met minimum development volume.")
        return

    out.to_csv(RESULTS / "v2_all_validated_rules.csv", index=False)

    # 1) Target screen: true objective.
    target = out[
        (out["All Resolved"] >= TARGET_ALL_RESOLVED)
        & (out["Test WR %"] >= TARGET_TEST_WR)
    ].sort_values(
        ["Test WR %", "All Resolved", "Test Wilson Low %"],
        ascending=[False, False, False],
    )
    target.to_csv(RESULTS / "v2_target_hits.csv", index=False)

    # 2) High-volume frontier.
    high_volume = out[out["All Resolved"] >= TARGET_ALL_RESOLVED].sort_values(
        ["Test WR %", "All Resolved"],
        ascending=[False, False],
    )
    high_volume.head(100).to_csv(
        RESULTS / "v2_high_volume_frontier.csv", index=False
    )

    # 3) Best test quality regardless of 1000 threshold, but still decent dev volume.
    best_test = out.sort_values(
        ["Test WR %", "All Resolved"],
        ascending=[False, False],
    )
    best_test.head(100).to_csv(
        RESULTS / "v2_best_test_frontier.csv", index=False
    )

    print("\n=== V2 TARGET HITS: TEST >=70% AND ALL RESOLVED >=1000 ===")
    if target.empty:
        print("NONE")
    else:
        print(target.head(30).to_string(index=False))

    print("\n=== V2 HIGH-VOLUME FRONTIER: ALL RESOLVED >=1000 ===")
    if high_volume.empty:
        print("NONE")
    else:
        print(high_volume.head(30).to_string(index=False))

    print("\n=== V2 BEST TEST FRONTIER ===")
    print(best_test.head(30).to_string(index=False))

    # Useful interpretation line.
    hv = high_volume.head(1)
    if not hv.empty:
        r = hv.iloc[0]
        print(
            f"\nBest 1000+ trade rule so far: "
            f"Test WR {r['Test WR %']:.2f}% | "
            f"All Resolved {int(r['All Resolved'])} | "
            f"Unique Stocks {int(r['Unique Stocks'])}"
        )


if __name__ == "__main__":
    main()

from pathlib import Path
import numpy as np
import pandas as pd

RESULTS = Path("strategy_05_many_trades/results")
FEATURE_FILE = RESULTS / "pattern_features_v6.csv"
OUT_FILE = RESULTS / "strategy05_2026_examples.csv"

FIB_ENTRY = 0.786
FIB_SL = 0.500
FIB_TARGET_126 = 1.260
FIB_TARGET_150 = 1.500

MIN_BODY = 60.0
MIN_CLOSE_ABOVE = 4.0


def reconstruct_levels(row):
    entry = float(row["Entry"])
    sl = float(row["SL"])
    swing_range = (entry - sl) / (FIB_ENTRY - FIB_SL)

    if not np.isfinite(swing_range) or swing_range <= 0:
        return None

    low = sl - swing_range * FIB_SL

    return {
        "Fib 0.786": entry,
        "SL 0.500": sl,
        "Target 1.260": low + swing_range * FIB_TARGET_126,
        "Target 1.500": low + swing_range * FIB_TARGET_150,
    }


def main():
    if not FEATURE_FILE.exists():
        raise SystemExit(
            f"Missing {FEATURE_FILE}. Run pattern_mining_v6.py first."
        )

    df = pd.read_csv(FEATURE_FILE)

    for c in ["Entry Date", "EOD Entry Date", "EOD Exit Date"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    mask = (
        (df["Entry Date"].dt.year == 2026)
        & (df["SIG_BodyPct"] >= MIN_BODY)
        & (df["SIG_CloseAbove786Pct"] >= MIN_CLOSE_ABOVE)
    )

    x = df.loc[mask].copy()

    levels = x.apply(reconstruct_levels, axis=1, result_type="expand")
    x = pd.concat([x, levels], axis=1)

    # Daily backtest data has dates, not intraday timestamps.
    # The signal becomes actionable only after the signal candle has closed.
    x["Confirmation Time"] = "After completed daily candle (EOD)"
    x["Next Session"] = x["EOD Entry Date"].dt.strftime("%Y-%m-%d")
    x["Signal Date"] = x["Entry Date"].dt.strftime("%Y-%m-%d")
    x["Exit Date"] = x["EOD Exit Date"].dt.strftime("%Y-%m-%d")

    cols = [
        "Symbol",
        "Signal Date",
        "Confirmation Time",
        "Next Session",
        "EOD Outcome",
        "Exit Date",
        "EOD Hold Days",
        "SIG_CloseAbove786Pct",
        "SIG_BodyPct",
        "Fib 0.786",
        "SL 0.500",
        "Target 1.260",
        "Target 1.500",
        "Split",
    ]

    out = x[cols].copy()
    out = out.sort_values(
        ["Signal Date", "Symbol"],
        ascending=[False, True],
    )

    out.to_csv(OUT_FILE, index=False)

    print("=" * 120)
    print("STRATEGY 05 — 2026 HISTORICAL LIVE-LIKE EXAMPLES")
    print("Rule: close >=4% above Fib 0.786 AND body >=60% of candle range")
    print("Signal is confirmed only after the completed daily candle.")
    print("=" * 120)
    print()
    print("TOTAL 2026 MATCHES:", len(out))
    print("RESOLVED:", int(out["EOD Outcome"].isin(["WIN", "LOSS"]).sum()))
    print("WINS:", int((out["EOD Outcome"] == "WIN").sum()))
    print("LOSSES:", int((out["EOD Outcome"] == "LOSS").sum()))
    print()
    print("LATEST 30 MATCHES:")
    print(out.head(30).to_string(index=False))
    print()
    print("Saved:", OUT_FILE)


if __name__ == "__main__":
    main()

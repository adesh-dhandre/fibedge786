import pandas as pd
import numpy as np

INPUT_FILE = "FIBEDGE_TOP_CURRENT_SETUPS.csv"
OUTPUT_FILE = "FIBEDGE_BEST_OPPORTUNITIES_V3.csv"

df = pd.read_csv(INPUT_FILE)


# ============================================================
# CURRENT POSITION / TIMING
# ============================================================

def current_state(row):

    status = str(row.get("Status", "")).upper()
    distance = row.get("Distance %", np.nan)

    if pd.isna(distance):
        return "UNKNOWN"

    # Explicitly handle NEAR 0.786
    if status == "NEAR 0.786":
        return "NEAR ENTRY"

    # Waiting setups
    if status == "WAITING FOR 0.786":

        if distance <= 2:
            return "NEAR ENTRY"

        if distance <= 5:
            return "CLOSE"

        if distance <= 10:
            return "WATCH"

        return "FAR"

    # Open setups
    if status == "OPEN":

        if abs(distance) <= 2:
            return "ENTRY ZONE"

        if distance > 2 and distance <= 8:
            return "ACTIVE"

        if distance > 8:
            return "EXTENDED"

        if distance < -2:
            return "BELOW ENTRY"

    return "OTHER"


# ============================================================
# OPPORTUNITY BUCKET
# ============================================================

def opportunity_bucket(row):

    grade = str(
        row.get("Live Grade", "C")
    )

    resolved = row.get(
        "Resolved Trades",
        0
    )

    win_rate = row.get(
        "Win Rate %",
        np.nan
    )

    expectancy = row.get(
        "Expectancy %",
        np.nan
    )

    state = row.get(
        "Current State",
        "UNKNOWN"
    )

    if pd.isna(resolved):
        resolved = 0

    if pd.isna(win_rate):
        win_rate = 0

    if pd.isna(expectancy):
        expectancy = -999

    actionable = state in [
        "NEAR ENTRY",
        "ENTRY ZONE",
        "ACTIVE"
    ]


    # ========================================================
    # ELITE NOW
    # ========================================================

    if (
        grade in ["A+", "A"]
        and resolved >= 10
        and win_rate >= 55
        and expectancy > 0
        and actionable
    ):
        return "ELITE NOW"


    # ========================================================
    # STRONG NOW
    # ========================================================

    if (
        grade in ["A+", "A", "B"]
        and resolved >= 8
        and win_rate >= 45
        and expectancy > 0
        and actionable
    ):
        return "STRONG NOW"


    # ========================================================
    # GOOD
    # ========================================================

    if (
        grade in ["A+", "A", "B"]
        and resolved >= 6
        and win_rate >= 40
        and expectancy > 0
        and state in [
            "NEAR ENTRY",
            "ENTRY ZONE",
            "ACTIVE",
            "CLOSE",
            "WATCH"
        ]
    ):
        return "GOOD"


    # ========================================================
    # WATCH
    # ========================================================

    if (
        grade in ["A+", "A", "B"]
        and resolved >= 6
        and win_rate >= 40
        and expectancy > 0
    ):
        return "WATCH"


    return "LOW PRIORITY"


# ============================================================
# SCORE
# ============================================================

def opportunity_score(row):

    quality = row.get(
        "Quality Score",
        np.nan
    )

    resolved = row.get(
        "Resolved Trades",
        0
    )

    win_rate = row.get(
        "Win Rate %",
        0
    )

    expectancy = row.get(
        "Expectancy %",
        0
    )

    median_days = row.get(
        "Median Win Days",
        np.nan
    )

    state = row.get(
        "Current State",
        "UNKNOWN"
    )

    if pd.isna(quality):
        quality = 0

    if pd.isna(resolved):
        resolved = 0

    if pd.isna(win_rate):
        win_rate = 0

    if pd.isna(expectancy):
        expectancy = 0


    score = 0.0


    # Historical quality - max 35
    score += (
        min(
            max(quality, 0),
            100
        )
        * 0.35
    )


    # Win rate - max 25
    score += (
        min(
            max(win_rate, 0),
            100
        )
        * 0.25
    )


    # Expectancy - max 15
    if expectancy > 0:

        score += (
            min(
                expectancy,
                10
            )
            / 10
            * 15
        )


    # Sample confidence - max 10
    if resolved >= 20:
        score += 10

    elif resolved >= 15:
        score += 8

    elif resolved >= 10:
        score += 6

    elif resolved >= 8:
        score += 4

    elif resolved >= 6:
        score += 2


    # Speed - max 10
    if not pd.isna(median_days):

        if median_days <= 3:
            score += 10

        elif median_days <= 5:
            score += 9

        elif median_days <= 7:
            score += 8

        elif median_days <= 10:
            score += 6

        elif median_days <= 15:
            score += 4

        elif median_days <= 20:
            score += 2


    # Current timing - max 5
    timing = {
        "NEAR ENTRY": 5,
        "ENTRY ZONE": 5,
        "ACTIVE": 4,
        "CLOSE": 3,
        "WATCH": 2,
        "FAR": 0,
        "EXTENDED": -4,
        "BELOW ENTRY": -5,
        "UNKNOWN": 0,
        "OTHER": 0
    }

    score += timing.get(
        state,
        0
    )

    return round(
        score,
        2
    )


# ============================================================
# APPLY
# ============================================================

df["Current State"] = df.apply(
    current_state,
    axis=1
)

df["Opportunity"] = df.apply(
    opportunity_bucket,
    axis=1
)

df["Opportunity Score V3"] = df.apply(
    opportunity_score,
    axis=1
)


# ============================================================
# SORT
# ============================================================

bucket_priority = {
    "ELITE NOW": 1,
    "STRONG NOW": 2,
    "GOOD": 3,
    "WATCH": 4,
    "LOW PRIORITY": 5
}

state_priority = {
    "NEAR ENTRY": 1,
    "ENTRY ZONE": 2,
    "ACTIVE": 3,
    "CLOSE": 4,
    "WATCH": 5,
    "FAR": 6,
    "EXTENDED": 7,
    "BELOW ENTRY": 8,
    "UNKNOWN": 9,
    "OTHER": 10
}

df["Bucket Priority"] = (
    df["Opportunity"]
    .map(bucket_priority)
    .fillna(99)
)

df["State Priority"] = (
    df["Current State"]
    .map(state_priority)
    .fillna(99)
)


df = df.sort_values(
    [
        "Bucket Priority",
        "State Priority",
        "Opportunity Score V3",
        "Quality Score",
        "Win Rate %",
        "Resolved Trades"
    ],
    ascending=[
        True,
        True,
        False,
        False,
        False,
        False
    ],
    na_position="last"
)


df.drop(
    columns=[
        "Bucket Priority",
        "State Priority"
    ],
    inplace=True
)


# ============================================================
# SAVE
# ============================================================

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# OUTPUT
# ============================================================

print("=" * 125)
print("FIBEDGE 786 - OPPORTUNITY RANKING V3")
print("=" * 125)

print()
print("OPPORTUNITY DISTRIBUTION")

print(
    df["Opportunity"]
    .value_counts()
    .to_string()
)

print()
print("CURRENT STATE DISTRIBUTION")

print(
    df["Current State"]
    .value_counts()
    .to_string()
)

print()
print("=" * 125)
print("TOP 40 ACTIONABLE SETUPS")
print("=" * 125)

top = df[
    df["Opportunity"].isin([
        "ELITE NOW",
        "STRONG NOW",
        "GOOD"
    ])
].copy()

columns = [
    "Symbol",
    "Status",
    "Current State",
    "Price",
    "Entry",
    "Distance %",
    "Live Grade",
    "Resolved Trades",
    "Win Rate %",
    "Expectancy %",
    "Median Win Days",
    "Speed Group",
    "Quality Score",
    "Opportunity Score V3",
    "Opportunity"
]

if top.empty:

    print(
        "No actionable high-quality setups."
    )

else:

    print(
        top[columns]
        .head(40)
        .round(2)
        .to_string(index=False)
    )

print()
print("Saved:", OUTPUT_FILE)
print("=" * 125)

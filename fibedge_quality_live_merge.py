import pandas as pd

LIVE_FILE = "FIBEDGE_LATEST_SIGNALS.csv"
QUALITY_FILE = "FIBEDGE_QUALITY_ALL_STOCKS.csv"
OUTPUT_FILE = "FIBEDGE_TOP_CURRENT_SETUPS.csv"

live = pd.read_csv(LIVE_FILE)
quality = pd.read_csv(QUALITY_FILE)

# Keep only current actionable / near-actionable setups
live_filtered = live[
    live["Status"].isin([
        "OPEN",
        "NEAR 0.786",
        "WAITING FOR 0.786"
    ])
].copy()

# Merge historical quality with current signal
merged = live_filtered.merge(
    quality,
    on="Symbol",
    how="left",
    suffixes=("", "_HIST")
)

# Production confidence rules
def production_grade(row):

    resolved = row.get("Resolved Trades", 0)
    win_rate = row.get("Win Rate %", 0)
    expectancy = row.get("Expectancy %", 0)
    score = row.get("Quality Score", 0)

    if pd.isna(resolved):
        return "INSUFFICIENT"

    if (
        resolved >= 10
        and score >= 75
        and win_rate >= 60
        and expectancy > 0
    ):
        return "A+"

    if (
        resolved >= 8
        and score >= 65
        and expectancy > 0
    ):
        return "A"

    if (
        resolved >= 6
        and score >= 55
        and expectancy > 0
    ):
        return "B"

    return "C"


def speed_group(row):

    days = row.get(
        "Median Win Days",
        None
    )

    if pd.isna(days):
        return "UNKNOWN"

    if days <= 7:
        return "FAST"

    if days <= 15:
        return "MEDIUM"

    return "SLOW"


merged["Live Grade"] = merged.apply(
    production_grade,
    axis=1
)

merged["Speed Group"] = merged.apply(
    speed_group,
    axis=1
)


# Ranking priority
status_priority = {
    "NEAR 0.786": 1,
    "OPEN": 2,
    "WAITING FOR 0.786": 3
}

grade_priority = {
    "A+": 1,
    "A": 2,
    "B": 3,
    "C": 4,
    "INSUFFICIENT": 5
}

speed_priority = {
    "FAST": 1,
    "MEDIUM": 2,
    "SLOW": 3,
    "UNKNOWN": 4
}


merged["Status Priority"] = (
    merged["Status"]
    .map(status_priority)
    .fillna(9)
)

merged["Grade Priority"] = (
    merged["Live Grade"]
    .map(grade_priority)
    .fillna(9)
)

merged["Speed Priority"] = (
    merged["Speed Group"]
    .map(speed_priority)
    .fillna(9)
)


merged = merged.sort_values(
    [
        "Grade Priority",
        "Status Priority",
        "Speed Priority",
        "Quality Score",
        "Win Rate %",
        "Distance %"
    ],
    ascending=[
        True,
        True,
        True,
        False,
        False,
        True
    ],
    na_position="last"
)


merged.drop(
    columns=[
        "Status Priority",
        "Grade Priority",
        "Speed Priority"
    ],
    inplace=True
)


merged.to_csv(
    OUTPUT_FILE,
    index=False
)


print("=" * 100)
print("FIBEDGE 786 - CURRENT QUALITY SETUPS")
print("=" * 100)

print()
print("Total current setups:", len(merged))

print()
print("LIVE GRADE DISTRIBUTION")

print(
    merged["Live Grade"]
    .value_counts()
    .to_string()
)

print()
print("SPEED DISTRIBUTION")

print(
    merged["Speed Group"]
    .value_counts()
    .to_string()
)


top = merged[
    merged["Live Grade"].isin(
        ["A+", "A"]
    )
].copy()


print()
print("=" * 100)
print("TOP QUALITY CURRENT SETUPS")
print("=" * 100)

columns = [
    "Symbol",
    "Status",
    "Price",
    "Entry",
    "Distance %",
    "Live Grade",
    "Quality Score",
    "Resolved Trades",
    "Win Rate %",
    "Expectancy %",
    "Median Win Days",
    "Fast <=10d %",
    "Speed Group"
]

if not top.empty:

    print(
        top[columns]
        .head(50)
        .round(2)
        .to_string(index=False)
    )

else:

    print(
        "No A+/A current setups."
    )


print()
print(
    "Saved:",
    OUTPUT_FILE
)

print("=" * 100)

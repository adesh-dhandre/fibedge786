import pandas as pd
import yfinance as yf
from datetime import datetime
import time

STRUCTURE_FILE = "ALL_NSE_CURRENT_SETUPS_V3.csv"
OUTPUT_FILE = "FIBEDGE_LATEST_SIGNALS.csv"

BATCH_SIZE = 200
NEAR_ENTRY_PCT = 2.0

print("=" * 80)
print("FIBEDGE 786 - FAST PRICE REFRESH")
print("=" * 80)

start_time = datetime.now()

df = pd.read_csv(STRUCTURE_FILE)

symbols = (
    df["Symbol"]
    .dropna()
    .astype(str)
    .drop_duplicates()
    .tolist()
)

print("Stocks:", len(symbols))
print()

latest_prices = {}
latest_times = {}

total_batches = (
    len(symbols) + BATCH_SIZE - 1
) // BATCH_SIZE

for batch_no, start in enumerate(
    range(0, len(symbols), BATCH_SIZE),
    1
):

    batch = symbols[start:start + BATCH_SIZE]

    print(
        f"Batch {batch_no}/{total_batches}"
        f" - {len(batch)} stocks"
    )

    try:

        data = yf.download(
            batch,
            period="5d",
            interval="5m",
            auto_adjust=False,
            progress=False,
            threads=True
        )

    except Exception as error:

        print("Batch failed:", error)
        continue

    for symbol in batch:

        try:

            if isinstance(data.columns, pd.MultiIndex):

                if symbol not in data.columns.get_level_values(1):
                    continue

                stock = data.xs(
                    symbol,
                    axis=1,
                    level=1
                )

            else:

                stock = data

            stock = stock.dropna(
                subset=["Close"]
            )

            if stock.empty:
                continue

            latest_prices[symbol] = float(
                stock["Close"].iloc[-1]
            )

            price_time = stock.index[-1]

            try:
                price_time = price_time.tz_convert(
                    "Asia/Kolkata"
                )
            except Exception:
                pass

            latest_times[symbol] = (
                price_time.isoformat()
            )

        except Exception:
            continue

    time.sleep(0.3)


def classify(row):

    symbol = row["Symbol"]

    if symbol not in latest_prices:
        return pd.Series([
            row.get("Price"),
            row.get("Price Time"),
            row.get("Status"),
            row.get("Distance %")
        ])

    price = latest_prices[symbol]

    entry = row.get("Entry")
    sl = row.get("SL")
    target = row.get("Target")

    old_status = row.get("Status")

    if (
        pd.isna(entry)
        or pd.isna(sl)
        or pd.isna(target)
    ):
        return pd.Series([
            price,
            latest_times.get(symbol),
            "NO CURRENT SETUP",
            None
        ])

    if old_status == "OPEN":

        distance = (
            (price - entry)
            / entry
            * 100
        )

        if price <= sl:
            status = "SL HIT"

        elif price >= target:
            status = "TARGET HIT"

        else:
            status = "OPEN"

    else:

        distance = (
            (entry - price)
            / entry
            * 100
        )

        if price >= entry:
            status = "ENTRY AREA"

        elif distance <= NEAR_ENTRY_PCT:
            status = "NEAR 0.786"

        else:
            status = "WAITING FOR 0.786"

    return pd.Series([
        price,
        latest_times.get(symbol),
        status,
        distance
    ])


df[
    [
        "Price",
        "Price Time",
        "Status",
        "Distance %"
    ]
] = df.apply(
    classify,
    axis=1
)


priority = {
    "TARGET HIT": 1,
    "SL HIT": 2,
    "OPEN": 3,
    "NEAR 0.786": 4,
    "ENTRY AREA": 5,
    "WAITING FOR 0.786": 6,
    "NO CURRENT SETUP": 7
}

df["Priority"] = (
    df["Status"]
    .map(priority)
    .fillna(9)
)

df = df.sort_values(
    ["Priority", "Distance %"],
    na_position="last"
)

df.drop(
    columns=["Priority"],
    inplace=True
)

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print()
print("=" * 80)
print("SIGNAL SUMMARY")
print("=" * 80)

print(
    df["Status"]
    .value_counts()
    .to_string()
)

duration = (
    datetime.now() - start_time
).total_seconds()

print()
print("Updated prices:", len(latest_prices))
print("Saved:", OUTPUT_FILE)
print(
    "Refresh time:",
    round(duration, 2),
    "seconds"
)
print("=" * 80)

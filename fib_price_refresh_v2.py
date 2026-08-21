import pandas as pd
import yfinance as yf
from datetime import datetime
import time
import gc

STRUCTURE_FILE = "ALL_NSE_CURRENT_SETUPS_V3.csv"
OUTPUT_FILE = "FIBEDGE_LATEST_SIGNALS.csv"

# Keep batches intentionally small for Render Free memory
BATCH_SIZE = 25

NEAR_ENTRY_PCT = 2.0

print("=" * 80)
print("FIBEDGE 786 - LOW MEMORY PRICE REFRESH V2")
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
print("Batch size:", BATCH_SIZE)
print("Price data: Yahoo 5-minute / 1-day")
print()

latest_prices = {}
latest_times = {}

total_batches = (
    len(symbols) + BATCH_SIZE - 1
) // BATCH_SIZE


def process_download(data, batch):

    if data is None or data.empty:
        return 0

    updated = 0

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

                # Only valid when the batch has one symbol
                stock = data

            stock = stock.dropna(
                subset=["Close"]
            )

            if stock.empty:
                continue

            latest_price = float(
                stock["Close"].iloc[-1]
            )

            price_time = stock.index[-1]

            try:

                price_time = price_time.tz_convert(
                    "Asia/Kolkata"
                )

            except Exception:
                pass

            latest_prices[symbol] = latest_price

            latest_times[symbol] = (
                price_time.isoformat()
            )

            updated += 1

        except Exception:
            continue

    return updated


for batch_no, start in enumerate(
    range(0, len(symbols), BATCH_SIZE),
    1
):

    batch = symbols[
        start:start + BATCH_SIZE
    ]

    print(
        f"Batch {batch_no}/{total_batches}"
        f" - {len(batch)} stocks"
    )

    data = None

    try:

        # Normally we only need today's intraday candles.
        data = yf.download(
            batch,
            period="1d",
            interval="5m",
            auto_adjust=False,
            progress=False,
            threads=True
        )

        updated = process_download(
            data,
            batch
        )

        # If today has no data, for example weekend/holiday,
        # retry this small batch using the last 5 days.
        if updated == 0:

            del data
            gc.collect()

            data = yf.download(
                batch,
                period="5d",
                interval="5m",
                auto_adjust=False,
                progress=False,
                threads=True
            )

            updated = process_download(
                data,
                batch
            )

    except Exception as error:

        print(
            "   Download error:",
            str(error)[:120]
        )

    finally:

        if data is not None:
            del data

        gc.collect()

    print(
        "   Prices available:",
        len(latest_prices),
        "/",
        len(symbols)
    )

    time.sleep(0.15)


def classify(row):

    symbol = row["Symbol"]

    # If Yahoo failed for this particular stock,
    # keep the previous saved data instead of destroying it.
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

    old_status = str(
        row.get("Status", "")
    )

    price_time = latest_times.get(
        symbol
    )

    if (
        pd.isna(entry)
        or pd.isna(sl)
        or pd.isna(target)
    ):

        return pd.Series([
            price,
            price_time,
            "NO CURRENT SETUP",
            None
        ])

    entry = float(entry)
    sl = float(sl)
    target = float(target)

    # Existing triggered/open setup
    if old_status in [
        "OPEN",
        "SL HIT",
        "TARGET HIT"
    ]:

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
        price_time,
        status,
        distance
    ])


print()
print("Recalculating signal statuses...")

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
    [
        "Priority",
        "Distance %"
    ],
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

duration = (
    datetime.now() - start_time
).total_seconds()

print()
print("=" * 80)
print("SIGNAL SUMMARY")
print("=" * 80)

print(
    df["Status"]
    .value_counts()
    .to_string()
)

print()
print(
    "Updated prices:",
    len(latest_prices)
)

print(
    "Missing prices:",
    len(symbols) - len(latest_prices)
)

print(
    "Saved:",
    OUTPUT_FILE
)

print(
    "Refresh time:",
    round(duration, 2),
    "seconds"
)

print("=" * 80)
print("FibEdge V2 low-memory refresh complete")
print("=" * 80)

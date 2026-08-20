import pandas as pd
import yfinance as yf
import time
from datetime import datetime

UNIVERSE_FILE = "NSE_STOCK_UNIVERSE.csv"
OUTPUT_FILE = "ALL_NSE_CURRENT_SETUPS_V3.csv"
FAILED_FILE = "ALL_NSE_FAILED_SYMBOLS_V3.csv"

BATCH_SIZE = 100

MIN_DECLINE = 0.08
MIN_SWING_DAYS = 15

FIB_ENTRY = 0.786
FIB_SL = 0.500
FIB_TARGET = 1.260

NEAR_ENTRY_PCT = 2.0


def extract_symbol(downloaded, symbol):

    if downloaded is None or downloaded.empty:
        return None

    try:
        if isinstance(downloaded.columns, pd.MultiIndex):
            if symbol not in downloaded.columns.get_level_values(1):
                return None

            df = downloaded.xs(
                symbol,
                axis=1,
                level=1
            ).copy()
        else:
            df = downloaded.copy()

        df = df.dropna(how="all")

        if df.empty:
            return None

        return df

    except Exception:
        return None


def find_setup(df):

    if df is None or len(df) < 40:
        return None

    df = df.copy().reset_index()

    date_column = df.columns[0]

    df[date_column] = pd.to_datetime(
        df[date_column]
    )

    high_price = float(df.loc[0, "High"])
    high_date = df.loc[0, date_column]

    state = "SEARCH_HIGH"

    low_price = None
    low_date = None
    low_idx = None

    entry = None
    sl = None
    target = None
    entry_date = None

    for i in range(1, len(df)):

        date = df.loc[i, date_column]
        candle_high = float(df.loc[i, "High"])
        candle_low = float(df.loc[i, "Low"])

        if state == "SEARCH_HIGH":

            if candle_high > high_price:
                high_price = candle_high
                high_date = date

            decline = (
                high_price - candle_low
            ) / high_price

            days = (
                date - high_date
            ).days

            if (
                decline >= MIN_DECLINE
                and days >= MIN_SWING_DAYS
            ):
                state = "TRACK_LOW"

                low_price = candle_low
                low_date = date
                low_idx = i


        elif state == "TRACK_LOW":

            if candle_low < low_price:
                low_price = candle_low
                low_date = date
                low_idx = i

            price_range = (
                high_price - low_price
            )

            sl = (
                low_price
                + price_range * FIB_SL
            )

            entry = (
                low_price
                + price_range * FIB_ENTRY
            )

            target = (
                low_price
                + price_range * FIB_TARGET
            )

            if i <= low_idx:
                continue

            if candle_high >= entry:

                entry_date = date

                if (
                    candle_low <= sl
                    or candle_high >= target
                ):
                    state = "SEARCH_HIGH"

                    high_price = candle_high
                    high_date = date

                    low_price = None
                    low_date = None
                    low_idx = None

                    entry = None
                    sl = None
                    target = None
                    entry_date = None

                else:
                    state = "OPEN"


        elif state == "OPEN":

            if (
                candle_low <= sl
                or candle_high >= target
            ):
                state = "SEARCH_HIGH"

                high_price = candle_high
                high_date = date

                low_price = None
                low_date = None
                low_idx = None

                entry = None
                sl = None
                target = None
                entry_date = None


    if state == "TRACK_LOW":

        price_range = (
            high_price - low_price
        )

        return {
            "Structure": "TRACKING",

            "High Date":
                high_date.date(),

            "High":
                high_price,

            "Low Date":
                low_date.date(),

            "Low":
                low_price,

            "Entry Date":
                None,

            "Entry":
                low_price
                + price_range * FIB_ENTRY,

            "SL":
                low_price
                + price_range * FIB_SL,

            "Target":
                low_price
                + price_range * FIB_TARGET
        }


    if state == "OPEN":

        return {
            "Structure": "OPEN",

            "High Date":
                high_date.date(),

            "High":
                high_price,

            "Low Date":
                low_date.date(),

            "Low":
                low_price,

            "Entry Date":
                entry_date.date()
                if entry_date is not None
                else None,

            "Entry":
                entry,

            "SL":
                sl,

            "Target":
                target
        }


    return None


def classify(setup, price):

    if setup is None:
        return "NO CURRENT SETUP", None

    entry = setup["Entry"]
    sl = setup["SL"]
    target = setup["Target"]


    if setup["Structure"] == "OPEN":

        distance = (
            (price - entry)
            / entry
            * 100
        )

        if price <= sl:
            return "SL HIT", distance

        if price >= target:
            return "TARGET HIT", distance

        return "OPEN", distance


    distance = (
        (entry - price)
        / entry
        * 100
    )


    if price >= entry:
        return "ENTRY AREA", distance

    if distance <= NEAR_ENTRY_PCT:
        return "NEAR 0.786", distance

    return "WAITING FOR 0.786", distance


print("=" * 90)
print("FIBEDGE 786 - FULL NSE SCANNER V3")
print("=" * 90)

start_time = datetime.now()

universe = pd.read_csv(
    UNIVERSE_FILE
)

symbols = (
    universe["YF_SYMBOL"]
    .dropna()
    .astype(str)
    .str.strip()
    .drop_duplicates()
    .tolist()
)

print("Total NSE stocks:", len(symbols))
print("Latest price source: Yahoo 5-minute")
print()


results = []
failed = []


total_batches = (
    len(symbols)
    + BATCH_SIZE - 1
) // BATCH_SIZE


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


    try:

        daily = yf.download(
            batch,
            period="1y",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=True
        )


        intraday = yf.download(
            batch,
            period="5d",
            interval="5m",
            auto_adjust=False,
            progress=False,
            threads=True
        )

    except Exception as error:

        print("Batch failed:", error)

        failed.extend(batch)

        continue


    for symbol in batch:

        try:

            daily_df = extract_symbol(
                daily,
                symbol
            )

            intraday_df = extract_symbol(
                intraday,
                symbol
            )


            if (
                daily_df is None
                or intraday_df is None
            ):
                failed.append(symbol)
                continue


            intraday_df = (
                intraday_df
                .dropna(subset=["Close"])
            )


            if intraday_df.empty:
                failed.append(symbol)
                continue


            latest_price = float(
                intraday_df["Close"].iloc[-1]
            )

            price_time = (
                intraday_df.index[-1]
            )


            try:

                price_time = (
                    price_time
                    .tz_convert(
                        "Asia/Kolkata"
                    )
                )

            except Exception:
                pass


            setup = find_setup(
                daily_df
            )


            status, distance = classify(
                setup,
                latest_price
            )


            row = {

                "Symbol":
                    symbol,

                "Price":
                    latest_price,

                "Price Time":
                    price_time.isoformat(),

                "Status":
                    status,

                "High Date":
                    setup["High Date"]
                    if setup
                    else None,

                "High":
                    setup["High"]
                    if setup
                    else None,

                "Low Date":
                    setup["Low Date"]
                    if setup
                    else None,

                "Low":
                    setup["Low"]
                    if setup
                    else None,

                "Entry Date":
                    setup["Entry Date"]
                    if setup
                    else None,

                "Entry":
                    setup["Entry"]
                    if setup
                    else None,

                "SL":
                    setup["SL"]
                    if setup
                    else None,

                "Target":
                    setup["Target"]
                    if setup
                    else None,

                "Distance %":
                    distance
            }


            results.append(row)


        except Exception:

            failed.append(symbol)


    print(
        "   Completed:",
        len(results),
        "| Failed:",
        len(failed)
    )

    time.sleep(1)


results_df = pd.DataFrame(results)

failed_df = pd.DataFrame({
    "Symbol": failed
})


if not results_df.empty:

    priority = {

        "TARGET HIT": 1,
        "SL HIT": 2,
        "OPEN": 3,
        "NEAR 0.786": 4,
        "ENTRY AREA": 5,
        "WAITING FOR 0.786": 6,
        "NO CURRENT SETUP": 7
    }


    results_df["Priority"] = (
        results_df["Status"]
        .map(priority)
        .fillna(9)
    )


    results_df = (
        results_df
        .sort_values(
            ["Priority", "Distance %"],
            na_position="last"
        )
    )


    results_df.drop(
        columns=["Priority"],
        inplace=True
    )


    results_df.to_csv(
        OUTPUT_FILE,
        index=False
    )


failed_df.to_csv(
    FAILED_FILE,
    index=False
)


print()
print("=" * 90)
print("SCAN SUMMARY")
print("=" * 90)

print("Successful:", len(results_df))
print("Failed:", len(failed_df))


if not results_df.empty:

    print()

    print(
        results_df["Status"]
        .value_counts()
        .to_string()
    )


print()
print("Saved:", OUTPUT_FILE)
print("Saved:", FAILED_FILE)

duration = (
    datetime.now()
    - start_time
).total_seconds()


print(
    "Duration:",
    round(duration / 60, 2),
    "minutes"
)

print("=" * 90)
print("FibEdge 786 V3 complete")
print("=" * 90)

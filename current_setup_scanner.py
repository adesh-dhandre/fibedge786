import pandas as pd
import yfinance as yf
import time

# ============================================================
# CURRENT NSE FIBONACCI SETUP SCANNER
# ============================================================

STOCKS = [
    "HEG.NS",
    "BHARTIARTL.NS",
    "HCG.NS",
    "ANANTRAJ.NS",
    "GOKEX.NS",
    "RELIANCE.NS",
    "TCS.NS",
    "SBIN.NS",
    "TATASTEEL.NS",
    "ICICIBANK.NS"
]

PERIOD = "3y"
INTERVAL = "1d"

# LOCKED STRATEGY
MIN_DECLINE = 0.08
MIN_SWING_DAYS = 15

FIB_ENTRY = 0.786
FIB_SL = 0.500
FIB_TARGET = 1.260

# If current price is within 2% below entry
# we call it NEAR ENTRY.
NEAR_ENTRY_PCT = 2.0


def download_data(symbol):

    try:

        df = yf.download(
            symbol,
            period=PERIOD,
            interval=INTERVAL,
            auto_adjust=False,
            progress=False
        )

        if df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.reset_index()

        required = [
            "Date",
            "Open",
            "High",
            "Low",
            "Close"
        ]

        for col in required:

            if col not in df.columns:
                return None

        df = df[required].copy()

        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

        for col in [
            "Open",
            "High",
            "Low",
            "Close"
        ]:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

        df = df.dropna(
            subset=required
        ).reset_index(drop=True)

        return df

    except Exception as e:

        print(
            "Download error:",
            symbol,
            e
        )

        return None


def analyze_stock(symbol, df):

    state = "SEARCH_HIGH"

    high_price = float(
        df.loc[0, "High"]
    )

    high_date = df.loc[
        0,
        "Date"
    ]

    low_price = None
    low_date = None
    low_idx = None

    entry = None
    sl = None
    target = None

    entry_date = None

    last_setup = None

    # ========================================================
    # PROCESS EVERY DAILY CANDLE
    # ========================================================

    for i in range(1, len(df)):

        date = df.loc[i, "Date"]

        candle_high = float(
            df.loc[i, "High"]
        )

        candle_low = float(
            df.loc[i, "Low"]
        )

        # ====================================================
        # SEARCH FOR MEANINGFUL HIGH
        # ====================================================

        if state == "SEARCH_HIGH":

            if candle_high > high_price:

                high_price = candle_high
                high_date = date

            decline = (
                high_price - candle_low
            ) / high_price

            days_from_high = (
                date - high_date
            ).days

            if (
                decline >= MIN_DECLINE
                and
                days_from_high >= MIN_SWING_DAYS
            ):

                state = "TRACK_LOW"

                low_price = candle_low
                low_date = date
                low_idx = i

        # ====================================================
        # TRACK LOW
        # ====================================================

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

            # ================================================
            # ENTRY TOUCH
            # ================================================

            if candle_high >= entry:

                entry_date = date

                # Entry candle ambiguity
                entry_hit_sl = (
                    candle_low <= sl
                )

                entry_hit_target = (
                    candle_high >= target
                )

                if (
                    entry_hit_sl
                    or
                    entry_hit_target
                ):

                    last_setup = {
                        "Status": "AMBIGUOUS",
                        "High Date": high_date,
                        "High": high_price,
                        "Low Date": low_date,
                        "Low": low_price,
                        "Entry Date": entry_date,
                        "Entry": entry,
                        "SL": sl,
                        "Target": target
                    }

                    state = "SEARCH_HIGH"

                    high_price = candle_high
                    high_date = date

                    low_price = None
                    low_date = None
                    low_idx = None

                else:

                    state = "OPEN_TRADE"

        # ====================================================
        # OPEN TRADE
        # ====================================================

        elif state == "OPEN_TRADE":

            hit_target = (
                candle_high >= target
            )

            hit_sl = (
                candle_low <= sl
            )

            if hit_target and hit_sl:

                last_setup = {
                    "Status": "AMBIGUOUS",
                    "High Date": high_date,
                    "High": high_price,
                    "Low Date": low_date,
                    "Low": low_price,
                    "Entry Date": entry_date,
                    "Entry": entry,
                    "SL": sl,
                    "Target": target
                }

                state = "SEARCH_HIGH"

                high_price = candle_high
                high_date = date

            elif hit_target:

                last_setup = {
                    "Status": "TARGET HIT",
                    "High Date": high_date,
                    "High": high_price,
                    "Low Date": low_date,
                    "Low": low_price,
                    "Entry Date": entry_date,
                    "Entry": entry,
                    "SL": sl,
                    "Target": target
                }

                state = "SEARCH_HIGH"

                high_price = candle_high
                high_date = date

            elif hit_sl:

                last_setup = {
                    "Status": "SL HIT",
                    "High Date": high_date,
                    "High": high_price,
                    "Low Date": low_date,
                    "Low": low_price,
                    "Entry Date": entry_date,
                    "Entry": entry,
                    "SL": sl,
                    "Target": target
                }

                state = "SEARCH_HIGH"

                high_price = candle_high
                high_date = date


    # ========================================================
    # CURRENT MARKET STATUS
    # ========================================================

    current_date = df["Date"].iloc[-1]

    current_price = float(
        df["Close"].iloc[-1]
    )

    # --------------------------------------------------------
    # ACTIVE OPEN TRADE
    # --------------------------------------------------------

    if state == "OPEN_TRADE":

        status = "OPEN"

        return {
            "Symbol": symbol,
            "Date": current_date.date(),
            "Price": current_price,
            "Status": status,
            "High": high_price,
            "Low": low_price,
            "Entry": entry,
            "SL": sl,
            "Target": target,
            "Distance %": (
                (current_price - entry)
                / entry
                * 100
            )
        }

    # --------------------------------------------------------
    # CURRENT FORMING SETUP
    # --------------------------------------------------------

    if state == "TRACK_LOW":

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

        distance_pct = (
            (entry - current_price)
            / entry
            * 100
        )

        if (
            current_price < entry
            and
            distance_pct <= NEAR_ENTRY_PCT
        ):

            status = "NEAR 0.786"

        elif current_price < entry:

            status = "WAITING FOR 0.786"

        else:

            status = "ENTRY AREA"

        return {
            "Symbol": symbol,
            "Date": current_date.date(),
            "Price": current_price,
            "Status": status,
            "High": high_price,
            "Low": low_price,
            "Entry": entry,
            "SL": sl,
            "Target": target,
            "Distance %": distance_pct
        }

    # --------------------------------------------------------
    # NO ACTIVE FORMING SWING
    # --------------------------------------------------------

    return {
        "Symbol": symbol,
        "Date": current_date.date(),
        "Price": current_price,
        "Status": "NO CURRENT SETUP",
        "High": None,
        "Low": None,
        "Entry": None,
        "SL": None,
        "Target": None,
        "Distance %": None
    }


# ============================================================
# RUN SCANNER
# ============================================================

print()
print("=" * 80)
print("CURRENT NSE FIBONACCI SETUP SCANNER")
print("=" * 80)

print()
print("Locked strategy:")
print("Minimum decline : 8%")
print("Minimum days    : 15")
print("Entry           : 0.786")
print("Stop Loss       : 0.500")
print("Target          : 1.260")
print()


scanner_results = []

for number, symbol in enumerate(
    STOCKS,
    1
):

    print(
        f"[{number}/{len(STOCKS)}] "
        f"Scanning {symbol}..."
    )

    df = download_data(
        symbol
    )

    if df is None:

        print(
            "   Skipped"
        )

        continue

    result = analyze_stock(
        symbol,
        df
    )

    scanner_results.append(
        result
    )

    print(
        "   Status:",
        result["Status"]
    )

    time.sleep(0.3)


# ============================================================
# OUTPUT TABLE
# ============================================================

results = pd.DataFrame(
    scanner_results
)

print()
print("=" * 80)
print("CURRENT SETUPS")
print("=" * 80)
print()

if results.empty:

    print(
        "No stocks scanned."
    )

else:

    priority = {
        "OPEN": 1,
        "NEAR 0.786": 2,
        "ENTRY AREA": 3,
        "WAITING FOR 0.786": 4,
        "NO CURRENT SETUP": 5
    }

    results["Priority"] = (
        results["Status"]
        .map(priority)
        .fillna(9)
    )

    results = results.sort_values(
        [
            "Priority",
            "Distance %"
        ],
        na_position="last"
    )

    display_columns = [
        "Symbol",
        "Price",
        "Status",
        "High",
        "Low",
        "Entry",
        "SL",
        "Target",
        "Distance %"
    ]

    print(
        results[
            display_columns
        ].to_string(
            index=False
        )
    )

    results.drop(
        columns=["Priority"],
        inplace=True
    )

    results.to_csv(
        "CURRENT_NSE_FIB_SETUPS.csv",
        index=False
    )

    print()
    print(
        "Saved: CURRENT_NSE_FIB_SETUPS.csv"
    )


print()
print("=" * 80)
print("Scanner complete")
print("=" * 80)

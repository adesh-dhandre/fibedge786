from io import StringIO
from pathlib import Path

import pandas as pd
import requests

# FibEdge 786 dashboard universe mapping
# --------------------------------------
# Creates one row per stock in NSE_STOCK_UNIVERSE.csv and adds independent
# membership flags for NIFTY 50, F&O, NIFTY Smallcap 250 and NIFTY Microcap 250.
# A stock may belong to more than one group.

BASE_DIR = Path(__file__).resolve().parent
MASTER_FILE = BASE_DIR / "NSE_STOCK_UNIVERSE.csv"
OUTPUT_FILE = BASE_DIR / "STOCK_UNIVERSE_MAPPING.csv"

NIFTY_50_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty50list.csv"
SMALLCAP_250_URL = "https://www.niftyindices.com/IndexConstituent/ind_niftysmallcap250list.csv"
MICROCAP_250_URL = "https://www.niftyindices.com/IndexConstituent/ind_niftymicrocap250_list.csv"
FNO_URL = "https://nsearchives.nseindia.com/content/fo/NSE_FO_SosScheme.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/csv,text/plain,*/*",
}


def download_text(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return response.text.lstrip("\ufeff")


def read_nifty_symbols(url: str) -> set[str]:
    text = download_text(url)
    df = pd.read_csv(StringIO(text))
    if "Symbol" not in df.columns:
        raise ValueError(f"Symbol column missing from {url}")
    return set(df["Symbol"].dropna().astype(str).str.strip().str.upper())


def read_fno_symbols() -> set[str]:
    text = download_text(FNO_URL)

    # NSE_FO_SosScheme.csv begins with a date line before the CSV header.
    lines = text.splitlines()
    header_index = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("Symbol,")),
        None,
    )
    if header_index is None:
        raise ValueError("Could not find Symbol header in NSE F&O file")

    df = pd.read_csv(StringIO("\n".join(lines[header_index:])))
    if "Symbol" not in df.columns:
        raise ValueError("Symbol column missing from NSE F&O file")

    if "Symbol Type" in df.columns:
        df = df[df["Symbol Type"].astype(str).str.upper().eq("EQUITY")]

    return set(df["Symbol"].dropna().astype(str).str.strip().str.upper())


def yes_no(symbol: str, members: set[str]) -> str:
    return "YES" if symbol in members else "NO"


def main() -> None:
    if not MASTER_FILE.exists():
        raise FileNotFoundError(f"Missing master stock file: {MASTER_FILE.name}")

    master = pd.read_csv(MASTER_FILE)
    if "SYMBOL" not in master.columns:
        raise ValueError("SYMBOL column missing from NSE_STOCK_UNIVERSE.csv")

    symbols = master["SYMBOL"].dropna().astype(str).str.strip().str.upper()

    print("Downloading current official universe lists...")
    nifty50 = read_nifty_symbols(NIFTY_50_URL)
    smallcap250 = read_nifty_symbols(SMALLCAP_250_URL)
    microcap250 = read_nifty_symbols(MICROCAP_250_URL)
    fno = read_fno_symbols()

    mapping = pd.DataFrame({"SYMBOL": symbols}).drop_duplicates().sort_values("SYMBOL")
    mapping["NIFTY50"] = mapping["SYMBOL"].map(lambda s: yes_no(s, nifty50))
    mapping["FNO"] = mapping["SYMBOL"].map(lambda s: yes_no(s, fno))
    mapping["SMALLCAP250"] = mapping["SYMBOL"].map(lambda s: yes_no(s, smallcap250))
    mapping["MICROCAP250"] = mapping["SYMBOL"].map(lambda s: yes_no(s, microcap250))

    mapping.to_csv(OUTPUT_FILE, index=False)

    print(f"Created: {OUTPUT_FILE.name}")
    print(f"Total NSE symbols: {len(mapping)}")
    print(f"NIFTY 50 matched: {(mapping['NIFTY50'] == 'YES').sum()}")
    print(f"F&O matched: {(mapping['FNO'] == 'YES').sum()}")
    print(f"Smallcap 250 matched: {(mapping['SMALLCAP250'] == 'YES').sum()}")
    print(f"Microcap 250 matched: {(mapping['MICROCAP250'] == 'YES').sum()}")


if __name__ == "__main__":
    main()

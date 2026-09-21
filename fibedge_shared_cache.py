import base64
import json
import os
import sqlite3
import time
import zlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

IST = timezone(timedelta(hours=5, minutes=30))

CACHE_DIR = Path(".fibedge_cache")
SQLITE_FILE = CACHE_DIR / "market_cache.sqlite3"

FULL_PERIOD = "1y"
INCREMENTAL_PERIOD = "5d"
BATCH_SIZE = int(os.environ.get("FIBEDGE_YF_BATCH_SIZE", "125"))
MAX_CALENDAR_DAYS = 370


def now_ist():
    return datetime.now(IST)


def _encode_df(df):
    if df is None or df.empty:
        return None

    rows = []
    for row in df.itertuples(index=False):
        rows.append([
            pd.Timestamp(row.Date).strftime("%Y-%m-%d"),
            float(row.Open),
            float(row.High),
            float(row.Low),
            float(row.Close),
            float(row.Volume) if hasattr(row, "Volume") and pd.notna(row.Volume) else None,
        ])

    payload = {
        "v": 1,
        "rows": rows,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, level=6)).decode("ascii")


def _decode_df(payload):
    if not payload:
        return None

    try:
        raw = zlib.decompress(base64.b64decode(payload))
        obj = json.loads(raw.decode("utf-8"))
        rows = obj.get("rows") or []
        if not rows:
            return None

        df = pd.DataFrame(
            rows,
            columns=["Date", "Open", "High", "Low", "Close", "Volume"],
        )
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return (
            df.dropna(subset=["Date", "Open", "High", "Low", "Close"])
            .sort_values("Date")
            .drop_duplicates(subset=["Date"], keep="last")
            .reset_index(drop=True)
        )
    except Exception:
        return None


class SQLiteCache:
    def __init__(self, path=SQLITE_FILE):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_cache (
                    symbol TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )

    def load_many(self, symbols):
        out = {}
        if not symbols:
            return out

        with self._connect() as conn:
            for start in range(0, len(symbols), 400):
                chunk = symbols[start:start + 400]
                marks = ",".join("?" for _ in chunk)
                rows = conn.execute(
                    "SELECT symbol, payload FROM market_cache WHERE symbol IN (" + marks + ")",
                    chunk,
                ).fetchall()

                for symbol, payload in rows:
                    df = _decode_df(payload)
                    if df is not None and not df.empty:
                        out[symbol] = df

        return out

    def save_many(self, frames):
        now_ts = time.time()
        rows = []

        for symbol, df in frames.items():
            payload = _encode_df(df)
            if payload:
                rows.append((symbol, payload, now_ts))

        if not rows:
            return

        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO market_cache(symbol, payload, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                  payload=excluded.payload,
                  updated_at=excluded.updated_at
                """,
                rows,
            )

    def get_meta(self, key):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM cache_meta WHERE key=?",
                (key,),
            ).fetchone()
        return row[0] if row else None

    def set_meta(self, key, value):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cache_meta(key, value)
                VALUES(?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, str(value)),
            )


class UpstashRedisCache:
    def __init__(self):
        self.url = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
        self.token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

        if not self.url or not self.token:
            raise RuntimeError(
                "Redis cache requested but UPSTASH_REDIS_REST_URL / "
                "UPSTASH_REDIS_REST_TOKEN are missing."
            )

        self.headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
            "User-Agent": "FibEdge-786",
        }

    def _pipeline(self, commands):
        r = requests.post(
            self.url + "/pipeline",
            headers=self.headers,
            json=commands,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()

    def load_many(self, symbols):
        out = {}
        for start in range(0, len(symbols), 100):
            chunk = symbols[start:start + 100]
            commands = [["GET", "fibedge:market:" + s] for s in chunk]
            results = self._pipeline(commands)

            for symbol, result in zip(chunk, results):
                payload = result.get("result") if isinstance(result, dict) else None
                df = _decode_df(payload)
                if df is not None and not df.empty:
                    out[symbol] = df

        return out

    def save_many(self, frames):
        items = list(frames.items())
        for start in range(0, len(items), 50):
            chunk = items[start:start + 50]
            commands = []

            for symbol, df in chunk:
                payload = _encode_df(df)
                if payload:
                    commands.append(["SET", "fibedge:market:" + symbol, payload])

            if commands:
                self._pipeline(commands)

    def get_meta(self, key):
        r = requests.post(
            self.url,
            headers=self.headers,
            json=["GET", "fibedge:meta:" + key],
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("result")

    def set_meta(self, key, value):
        r = requests.post(
            self.url,
            headers=self.headers,
            json=["SET", "fibedge:meta:" + key, str(value)],
            timeout=30,
        )
        r.raise_for_status()


def get_cache():
    backend = os.environ.get("FIBEDGE_CACHE_BACKEND", "").strip().lower()

    if backend == "redis" or (
        not backend
        and os.environ.get("UPSTASH_REDIS_REST_URL")
        and os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    ):
        return UpstashRedisCache(), "redis"

    return SQLiteCache(), "sqlite"


def _extract_symbol(downloaded, symbol):
    if downloaded is None or downloaded.empty:
        return None

    try:
        if isinstance(downloaded.columns, pd.MultiIndex):
            levels0 = downloaded.columns.get_level_values(0)
            levels1 = downloaded.columns.get_level_values(1)

            if symbol in levels1:
                df = downloaded.xs(symbol, axis=1, level=1).copy()
            elif symbol in levels0:
                df = downloaded.xs(symbol, axis=1, level=0).copy()
            else:
                return None
        else:
            df = downloaded.copy()

        if df.empty:
            return None

        df = df.reset_index()
        date_col = df.columns[0]
        df.rename(columns={date_col: "Date"}, inplace=True)

        wanted = ["Date", "Open", "High", "Low", "Close"]
        if not all(col in df.columns for col in wanted):
            return None

        if "Volume" not in df.columns:
            df["Volume"] = None

        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return (
            df.dropna(subset=["Date", "Open", "High", "Low", "Close"])
            .sort_values("Date")
            .drop_duplicates(subset=["Date"], keep="last")
            .reset_index(drop=True)
        )
    except Exception:
        return None


def _merge(old, new):
    if old is None or old.empty:
        merged = new.copy()
    elif new is None or new.empty:
        merged = old.copy()
    else:
        merged = pd.concat([old, new], ignore_index=True)

    if merged is None or merged.empty:
        return None

    merged["Date"] = pd.to_datetime(merged["Date"], errors="coerce").dt.tz_localize(None)
    merged = (
        merged.dropna(subset=["Date", "Open", "High", "Low", "Close"])
        .sort_values("Date")
        .drop_duplicates(subset=["Date"], keep="last")
        .reset_index(drop=True)
    )

    max_date = merged["Date"].max()
    if pd.notna(max_date):
        cutoff = max_date - pd.Timedelta(days=MAX_CALENDAR_DAYS)
        merged = merged[merged["Date"] >= cutoff].reset_index(drop=True)

    return merged


def _download_batches(symbols, period):
    frames = {}
    failed = []

    total = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_no, start in enumerate(range(0, len(symbols), BATCH_SIZE), 1):
        batch = symbols[start:start + BATCH_SIZE]
        print(
            "Market cache",
            period,
            "batch",
            str(batch_no) + "/" + str(total),
            "-",
            len(batch),
            "stocks",
        )

        try:
            data = yf.download(
                batch,
                period=period,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="column",
            )
        except Exception as exc:
            print("  batch failed:", str(exc)[:160])
            failed.extend(batch)
            continue

        for symbol in batch:
            df = _extract_symbol(data, symbol)
            if df is None or df.empty:
                failed.append(symbol)
            else:
                frames[symbol] = df

    return frames, failed


def refresh_market_cache(symbols, force_full=False):
    started = time.time()
    cache, backend_name = get_cache()

    print("=" * 88)
    print("FIBEDGE SHARED 1-YEAR MARKET CACHE")
    print("=" * 88)
    print("Backend:", backend_name)
    print("Symbols:", len(symbols))
    print("Batch size:", BATCH_SIZE)

    existing = {} if force_full else cache.load_many(symbols)

    missing = [s for s in symbols if s not in existing]
    warm = [s for s in symbols if s in existing]

    print("Cached:", len(warm))
    print("Need 1-year seed:", len(missing))

    updated = dict(existing)
    failed = []

    if missing:
        full_frames, full_failed = _download_batches(missing, FULL_PERIOD)
        updated.update(full_frames)
        failed.extend(full_failed)

    if warm and not force_full:
        recent_frames, recent_failed = _download_batches(warm, INCREMENTAL_PERIOD)

        for symbol in warm:
            if symbol in recent_frames:
                updated[symbol] = _merge(existing.get(symbol), recent_frames[symbol])

        failed.extend(recent_failed)

    if force_full and not missing:
        full_frames, full_failed = _download_batches(symbols, FULL_PERIOD)
        updated = full_frames
        failed.extend(full_failed)

    # Save only normalized 1-year windows.
    cleaned = {}
    for symbol, df in updated.items():
        merged = _merge(None, df)
        if merged is not None and not merged.empty:
            cleaned[symbol] = merged

    cache.save_many(cleaned)
    finished = time.time()

    cache.set_meta("last_refresh_ist", now_ist().isoformat())
    cache.set_meta("last_refresh_seconds", round(finished - started, 3))
    cache.set_meta("last_refresh_backend", backend_name)

    stats = {
        "backend": backend_name,
        "symbols": len(symbols),
        "cached_before": len(warm),
        "seeded": len(missing),
        "available": len(cleaned),
        "failed": len(set(failed)),
        "duration_seconds": finished - started,
    }

    print("Available:", stats["available"])
    print("Failed:", stats["failed"])
    print("Cache refresh:", round(stats["duration_seconds"], 2), "sec")
    print("=" * 88)

    return cleaned, stats


def completed_daily(df, settle_hour=15, settle_minute=40):
    if df is None or df.empty:
        return df

    current = now_ist()
    today = pd.Timestamp(current.date())
    out = df.copy()

    if (current.hour, current.minute) < (settle_hour, settle_minute):
        out = out[out["Date"].dt.normalize() < today]

    return out.sort_values("Date").reset_index(drop=True)

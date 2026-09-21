import base64
import json
import os
import sqlite3
import time
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# Large batches + a few concurrent downloads are much faster than the old
# sequential 125-stock loop, while keeping memory reasonable on a laptop.
BATCH_SIZE = int(os.environ.get("FIBEDGE_YF_BATCH_SIZE", "300"))
DOWNLOAD_WORKERS = int(os.environ.get("FIBEDGE_YF_WORKERS", "4"))

# During market hours we permit a small freshness TTL. After the completed
# daily candle is available, one successful refresh is considered current
# for the rest of that IST calendar day.
INTRADAY_TTL_SECONDS = int(os.environ.get("FIBEDGE_INTRADAY_TTL_SECONDS", "300"))
SETTLE_HOUR = 15
SETTLE_MINUTE = 40
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
            float(row.Volume)
            if hasattr(row, "Volume") and pd.notna(row.Volume)
            else None,
        ])

    raw = json.dumps({"v": 1, "rows": rows}, separators=(",", ":")).encode("utf-8")
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

    def _command(self, command, timeout=60):
        r = requests.post(
            self.url,
            headers=self.headers,
            json=command,
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json().get("result")

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

        # MGET reduces thousands of cache reads to only a handful of HTTP calls.
        for start in range(0, len(symbols), 500):
            chunk = symbols[start:start + 500]
            keys = ["fibedge:market:" + s for s in chunk]
            values = self._command(["MGET"] + keys) or []

            for symbol, payload in zip(chunk, values):
                df = _decode_df(payload)
                if df is not None and not df.empty:
                    out[symbol] = df

        return out

    def save_many(self, frames):
        items = list(frames.items())
        for start in range(0, len(items), 100):
            chunk = items[start:start + 100]
            commands = []

            for symbol, df in chunk:
                payload = _encode_df(df)
                if payload:
                    commands.append(["SET", "fibedge:market:" + symbol, payload])

            if commands:
                self._pipeline(commands)

    def get_meta(self, key):
        return self._command(["GET", "fibedge:meta:" + key], timeout=30)

    def set_meta(self, key, value):
        self._command(["SET", "fibedge:meta:" + key, str(value)], timeout=30)


def get_cache():
    backend = os.environ.get("FIBEDGE_CACHE_BACKEND", "").strip().lower()

    if backend == "redis" or (
        not backend
        and os.environ.get("UPSTASH_REDIS_REST_URL")
        and os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    ):
        return UpstashRedisCache(), "redis"

    return SQLiteCache(), "sqlite"


def _parse_ist(value):
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=IST)
        return dt.astimezone(IST)
    except Exception:
        return None


def _cache_is_current(cache, now):
    # Support the metadata name written by the previous research build too.
    last = (
        cache.get_meta("market_last_refresh_ist")
        or cache.get_meta("last_refresh_ist")
    )
    last_dt = _parse_ist(last)

    if last_dt is None or last_dt.date() != now.date():
        return False, "different-day-or-no-refresh"

    now_after_settle = (now.hour, now.minute) >= (SETTLE_HOUR, SETTLE_MINUTE)
    last_after_settle = (
        last_dt.hour,
        last_dt.minute,
    ) >= (SETTLE_HOUR, SETTLE_MINUTE)

    if now_after_settle and last_after_settle:
        return True, "completed-daily-cache-current"

    age = max(0.0, (now - last_dt).total_seconds())
    if not now_after_settle and age <= INTRADAY_TTL_SECONDS:
        return True, "intraday-cache-ttl"

    return False, "refresh-required"


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
        merged = new.copy() if new is not None else None
    elif new is None or new.empty:
        merged = old.copy()
    else:
        merged = pd.concat([old, new], ignore_index=True)

    if merged is None or merged.empty:
        return None

    merged["Date"] = pd.to_datetime(
        merged["Date"],
        errors="coerce",
    ).dt.tz_localize(None)

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


def _download_one_batch(batch, period, batch_no, total):
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
        return {}, list(batch)

    frames = {}
    failed = []

    for symbol in batch:
        df = _extract_symbol(data, symbol)
        if df is None or df.empty:
            failed.append(symbol)
        else:
            frames[symbol] = df

    return frames, failed


def _download_batches(symbols, period):
    if not symbols:
        return {}, []

    batches = [
        symbols[start:start + BATCH_SIZE]
        for start in range(0, len(symbols), BATCH_SIZE)
    ]

    total = len(batches)
    workers = max(1, min(DOWNLOAD_WORKERS, total))
    frames = {}
    failed = []

    # Parallelize only across a few large batches. Yahoo still handles symbol
    # threads inside each batch, so this is deliberately bounded.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_download_one_batch, batch, period, i + 1, total): i
            for i, batch in enumerate(batches)
        }

        for future in as_completed(futures):
            try:
                batch_frames, batch_failed = future.result()
                frames.update(batch_frames)
                failed.extend(batch_failed)
            except Exception as exc:
                print("  worker failed:", str(exc)[:160])
                failed.extend(batches[futures[future]])

    return frames, failed


def refresh_market_cache(symbols, force_full=False):
    started = time.time()
    cache, backend_name = get_cache()
    current = now_ist()

    print("=" * 88)
    print("FIBEDGE SHARED 1-YEAR MARKET CACHE")
    print("=" * 88)
    print("Backend:", backend_name)
    print("Symbols:", len(symbols))
    print("Batch size:", BATCH_SIZE)
    print("Parallel download workers:", DOWNLOAD_WORKERS)

    existing = {} if force_full else cache.load_many(symbols)
    missing = [s for s in symbols if s not in existing]
    warm = [s for s in symbols if s in existing]

    is_current, freshness_reason = _cache_is_current(cache, current)

    print("Cached:", len(warm))
    print("Need 1-year seed:", len(missing))
    print("Freshness:", freshness_reason)

    # Fastest path: after one completed-daily refresh, repeated manual scans
    # use the exact same market snapshot and do ZERO Yahoo requests.
    if not force_full and not missing and is_current:
        generation = (
            cache.get_meta("market_generation")
            or cache.get_meta("market_last_refresh_ist")
            or cache.get_meta("last_refresh_ist")
            or current.isoformat()
        )
        elapsed = time.time() - started

        print("Yahoo download: SKIPPED (cache already current)")
        print("Cache load:", round(elapsed, 2), "sec")
        print("=" * 88)

        return existing, {
            "backend": backend_name,
            "symbols": len(symbols),
            "cached_before": len(warm),
            "seeded": 0,
            "available": len(existing),
            "failed": 0,
            "duration_seconds": elapsed,
            "network_skipped": True,
            "market_changed": False,
            "generation": generation,
            "freshness_reason": freshness_reason,
        }

    updated = dict(existing)
    failed = []
    network_used = False

    if missing:
        network_used = True
        full_frames, full_failed = _download_batches(missing, FULL_PERIOD)
        updated.update(full_frames)
        failed.extend(full_failed)

    # If the cache is stale, only warm symbols need the recent incremental
    # network refresh. A full one-year redownload is never done for them.
    if warm and (force_full or not is_current):
        network_used = True

        if force_full:
            full_frames, full_failed = _download_batches(symbols, FULL_PERIOD)
            updated = full_frames
            failed.extend(full_failed)
        else:
            recent_frames, recent_failed = _download_batches(
                warm,
                INCREMENTAL_PERIOD,
            )

            for symbol in warm:
                if symbol in recent_frames:
                    updated[symbol] = _merge(
                        existing.get(symbol),
                        recent_frames[symbol],
                    )

            # Failed incremental downloads keep their previous cached frame.
            failed.extend(recent_failed)

    cleaned = {}
    for symbol, df in updated.items():
        merged = _merge(None, df)
        if merged is not None and not merged.empty:
            cleaned[symbol] = merged

    # Save only when the market cache actually changed. This removes a large
    # amount of SQLite/Redis serialization work on repeated same-day scans.
    if network_used:
        cache.save_many(cleaned)

    finished_dt = now_ist()
    finished = time.time()

    if network_used:
        generation = finished_dt.isoformat()
        cache.set_meta("market_generation", generation)
        cache.set_meta("market_last_refresh_ist", finished_dt.isoformat())

        # Keep the old key populated for compatibility with the previous build.
        cache.set_meta("last_refresh_ist", finished_dt.isoformat())
        cache.set_meta("last_refresh_seconds", round(finished - started, 3))
        cache.set_meta("last_refresh_backend", backend_name)
    else:
        generation = (
            cache.get_meta("market_generation")
            or cache.get_meta("market_last_refresh_ist")
            or cache.get_meta("last_refresh_ist")
            or finished_dt.isoformat()
        )

    stats = {
        "backend": backend_name,
        "symbols": len(symbols),
        "cached_before": len(warm),
        "seeded": len(missing),
        "available": len(cleaned),
        "failed": len(set(failed)),
        "duration_seconds": finished - started,
        "network_skipped": not network_used,
        "market_changed": network_used,
        "generation": generation,
        "freshness_reason": freshness_reason,
    }

    print("Available:", stats["available"])
    print("Failed downloads:", stats["failed"])
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

"""
SQLite database helpers for storing and retrieving price history.
"""
import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "prices.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                scraped_date    TEXT NOT NULL,
                competitor      TEXT NOT NULL,
                category        TEXT,
                comp_family     TEXT,
                url             TEXT NOT NULL,
                our_family      TEXT,
                our_retail      REAL,
                comp_list_price REAL,
                comp_sale_price REAL,
                comp_active_price REAL,
                markdown_pct    REAL,
                vs_our_retail_pct REAL,
                notes           TEXT,
                scrape_status   TEXT DEFAULT 'ok',
                error_msg       TEXT,
                UNIQUE (scraped_date, url)
            )
        """)
        # Migrate: add unique constraint if missing (existing DB without it)
        try:
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_date_url_unique
                ON price_history (scraped_date, url)
            """)
        except Exception:
            pass  # index may already exist


def insert_results(rows: list[dict]):
    """Insert a list of scraped result dicts for today's run."""
    if not rows:
        return
    cols = [
        "scraped_date", "competitor", "category", "comp_family", "url",
        "our_family", "our_retail", "comp_list_price", "comp_sale_price",
        "comp_active_price", "markdown_pct", "vs_our_retail_pct",
        "notes", "scrape_status", "error_msg",
    ]
    placeholders = ", ".join("?" for _ in cols)
    col_names = ", ".join(cols)
    with get_conn() as conn:
        conn.executemany(
            f"INSERT OR REPLACE INTO price_history ({col_names}) VALUES ({placeholders})",
            [[r.get(c) for c in cols] for r in rows],
        )


def get_last_run_prices(exclude_date: str) -> dict[str, float]:
    """
    Returns {url: comp_active_price} for the most recent run
    that is NOT exclude_date. Used for change detection.
    """
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT url, comp_active_price
            FROM price_history
            WHERE scraped_date = (
                SELECT MAX(scraped_date) FROM price_history
                WHERE scraped_date < ?
            )
        """, (exclude_date,)).fetchall()
    return {r["url"]: r["comp_active_price"] for r in rows}


def get_all_history() -> list[dict]:
    """Return all rows as list of dicts, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM price_history ORDER BY scraped_date DESC, competitor, category"
        ).fetchall()
    return [dict(r) for r in rows]


def get_latest_run() -> list[dict]:
    """Return rows from the most recent scrape date."""
    with get_conn() as conn:
        latest = conn.execute(
            "SELECT MAX(scraped_date) as d FROM price_history"
        ).fetchone()["d"]
        if not latest:
            return []
        rows = conn.execute(
            "SELECT * FROM price_history WHERE scraped_date = ? ORDER BY competitor, category",
            (latest,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_available_dates() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT scraped_date FROM price_history ORDER BY scraped_date DESC"
        ).fetchall()
    return [r["scraped_date"] for r in rows]


# ──────────────────────────────────────────────────────────────────────────────
# Zoned retailers (Retailer N, Retailer M) — separate table so the unique key can include
# zone without disrupting the existing non-zoned price_history table.
# ──────────────────────────────────────────────────────────────────────────────

def init_zoned_db():
    """Create price_history_zoned table if it doesn't exist."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history_zoned (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                scraped_date      TEXT NOT NULL,
                zone              INTEGER NOT NULL,
                zip_code          TEXT NOT NULL,
                competitor        TEXT NOT NULL,
                category          TEXT,
                comp_family       TEXT,
                url               TEXT NOT NULL,
                our_family        TEXT,
                our_retail        REAL,
                comp_list_price   REAL,
                comp_sale_price   REAL,
                comp_active_price REAL,
                markdown_pct      REAL,
                vs_our_retail_pct REAL,
                notes             TEXT,
                scrape_status     TEXT DEFAULT 'ok',
                error_msg         TEXT,
                UNIQUE (scraped_date, url, zone, zip_code)
            )
        """)


def insert_zoned_results(rows: list[dict]):
    """Insert a list of zoned scrape result dicts."""
    if not rows:
        return
    cols = [
        "scraped_date", "zone", "zip_code", "competitor", "category",
        "comp_family", "url", "our_family", "our_retail",
        "comp_list_price", "comp_sale_price", "comp_active_price",
        "markdown_pct", "vs_our_retail_pct", "notes",
        "scrape_status", "error_msg",
    ]
    placeholders = ", ".join("?" for _ in cols)
    col_names = ", ".join(cols)
    with get_conn() as conn:
        conn.executemany(
            f"INSERT OR REPLACE INTO price_history_zoned ({col_names}) VALUES ({placeholders})",
            [[r.get(c) for c in cols] for r in rows],
        )


def get_last_run_zoned_prices(exclude_date: str) -> dict[tuple, float]:
    """
    Returns {(url, zone): comp_active_price} for the most recent zoned run
    that is NOT exclude_date. Used for week-over-week change detection.
    """
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT url, zone, zip_code, comp_active_price
            FROM price_history_zoned
            WHERE scraped_date = (
                SELECT MAX(scraped_date) FROM price_history_zoned
                WHERE scraped_date < ?
            )
        """, (exclude_date,)).fetchall()
    return {(r["url"], r["zone"], r["zip_code"]): r["comp_active_price"] for r in rows}


def get_all_zoned_history() -> list[dict]:
    """Return all zoned rows as list of dicts, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM price_history_zoned ORDER BY scraped_date DESC, zone, competitor, category"
        ).fetchall()
    return [dict(r) for r in rows]


def get_latest_zoned_run() -> list[dict]:
    """Return rows from the most recent zoned scrape date."""
    with get_conn() as conn:
        latest = conn.execute(
            "SELECT MAX(scraped_date) as d FROM price_history_zoned"
        ).fetchone()["d"]
        if not latest:
            return []
        rows = conn.execute(
            "SELECT * FROM price_history_zoned WHERE scraped_date = ? ORDER BY zone, competitor, category",
            (latest,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_available_zoned_dates() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT scraped_date FROM price_history_zoned ORDER BY scraped_date DESC"
        ).fetchall()
    return [r["scraped_date"] for r in rows]

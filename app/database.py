"""Storage layer for SONA gold rates — local SQLite.

Note: on Render's free tier the disk is ephemeral (wiped on every deploy and
after ~15 min idle), so accumulated history resets there. The market-trend chart
still works because Tanishq ships its own 30-day history. To persist per-store
history across restarts you'd point this at an external database.

Dates are computed in Python so queries stay correct regardless of server timezone.
"""
import aiosqlite
from datetime import date, timedelta
from app.config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS gold_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_name TEXT NOT NULL,
                store_slug TEXT NOT NULL,
                gold_22k REAL,
                gold_24k REAL,
                gold_18k REAL,
                unit TEXT DEFAULT 'per_gram',
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rate_date DATE NOT NULL,
                source_url TEXT,
                UNIQUE(store_slug, rate_date)
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_rate_date ON gold_rates(rate_date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_store_date ON gold_rates(store_slug, rate_date)")
        await db.commit()


async def save_rate(store_name, store_slug, gold_22k, gold_24k, gold_18k,
                    source_url, rate_date=None):
    rate_date = (rate_date or date.today()).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO gold_rates (store_name, store_slug, gold_22k, gold_24k, gold_18k, rate_date, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(store_slug, rate_date) DO UPDATE SET
                store_name = excluded.store_name,
                gold_22k = COALESCE(excluded.gold_22k, gold_rates.gold_22k),
                gold_24k = COALESCE(excluded.gold_24k, gold_rates.gold_24k),
                gold_18k = COALESCE(excluded.gold_18k, gold_rates.gold_18k),
                scraped_at = CURRENT_TIMESTAMP,
                source_url = excluded.source_url
        """, (store_name, store_slug, gold_22k, gold_24k, gold_18k, rate_date, source_url))
        await db.commit()


async def _fetch(sql, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(sql, params)
        return [dict(r) for r in await cur.fetchall()]


async def get_today_rates():
    return await _fetch("SELECT * FROM gold_rates WHERE rate_date = ? ORDER BY gold_22k ASC",
                        (date.today().isoformat(),))


async def get_yesterday_rates():
    return await _fetch("SELECT * FROM gold_rates WHERE rate_date = ? ORDER BY gold_22k ASC",
                        ((date.today() - timedelta(days=1)).isoformat(),))


async def get_history(days=30):
    return await _fetch(
        "SELECT * FROM gold_rates WHERE rate_date >= ? ORDER BY rate_date ASC, store_name ASC",
        ((date.today() - timedelta(days=days)).isoformat(),))


async def get_store_history(store_slug, days=30):
    return await _fetch(
        "SELECT * FROM gold_rates WHERE store_slug = ? ORDER BY rate_date DESC LIMIT ?",
        (store_slug, days))


async def get_available_dates():
    rows = await _fetch("SELECT DISTINCT rate_date FROM gold_rates ORDER BY rate_date DESC LIMIT 90")
    return [r["rate_date"] for r in rows]


async def prune_old(keep_days=120):
    """Bound the table so it never grows without limit."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM gold_rates WHERE rate_date < ?",
                         ((date.today() - timedelta(days=keep_days)).isoformat(),))
        await db.commit()

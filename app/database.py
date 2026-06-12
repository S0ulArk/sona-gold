import aiosqlite
from datetime import date
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
    rate_date = rate_date or date.today()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO gold_rates (store_name, store_slug, gold_22k, gold_24k, gold_18k, rate_date, source_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(store_slug, rate_date) DO UPDATE SET
                gold_22k = COALESCE(excluded.gold_22k, gold_rates.gold_22k),
                gold_24k = COALESCE(excluded.gold_24k, gold_rates.gold_24k),
                gold_18k = COALESCE(excluded.gold_18k, gold_rates.gold_18k),
                scraped_at = CURRENT_TIMESTAMP,
                source_url = excluded.source_url
        """, (store_name, store_slug, gold_22k, gold_24k, gold_18k,
              rate_date.isoformat(), source_url))
        await db.commit()


async def get_today_rates():
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM gold_rates WHERE rate_date = ? ORDER BY gold_22k ASC", (today,))
        return [dict(r) for r in await cur.fetchall()]


async def get_yesterday_rates():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM gold_rates WHERE rate_date = date('now','-1 day') ORDER BY gold_22k ASC")
        return [dict(r) for r in await cur.fetchall()]


async def get_history(days=30):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM gold_rates WHERE rate_date >= date('now', ?) ORDER BY rate_date ASC, store_name ASC",
            (f"-{days} days",))
        return [dict(r) for r in await cur.fetchall()]


async def get_store_history(store_slug, days=30):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM gold_rates WHERE store_slug = ? ORDER BY rate_date DESC LIMIT ?",
            (store_slug, days))
        return [dict(r) for r in await cur.fetchall()]


async def get_available_dates():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT DISTINCT rate_date FROM gold_rates ORDER BY rate_date DESC LIMIT 90")
        return [r[0] for r in await cur.fetchall()]

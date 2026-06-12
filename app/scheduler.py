import logging
from datetime import date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.scrapers import scrape_all
from app.database import save_rate
from app.config import SCRAPE_INTERVAL_HOURS

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def save_rate_with_history(rate):
    """Save today's rate plus any embedded historical rows (e.g. Tanishq's 30-day JSON)."""
    if rate.gold_22k or rate.gold_24k or rate.gold_18k:
        await save_rate(rate.store_name, rate.store_slug, rate.gold_22k,
                        rate.gold_24k, rate.gold_18k, rate.source_url)
    if rate.history:
        for row in rate.history:
            try:
                d = date.fromisoformat(row["date"])
            except Exception:
                continue
            await save_rate(rate.store_name, rate.store_slug,
                            row.get("gold_22k"), row.get("gold_24k"), row.get("gold_18k"),
                            rate.source_url, rate_date=d)


async def run_scrape_job():
    logger.info("Starting scheduled scrape job...")
    rates = await scrape_all()
    saved = 0
    for rate in rates:
        if rate.gold_22k or rate.gold_24k or rate.gold_18k:
            await save_rate_with_history(rate)
            saved += 1
    logger.info(f"Scrape complete: {saved}/{len(rates)} stores saved")


def start_scheduler():
    scheduler.add_job(run_scrape_job, "interval", hours=SCRAPE_INTERVAL_HOURS,
                      id="scrape_gold_rates", replace_existing=True)
    scheduler.start()
    logger.info(f"Scheduler started: every {SCRAPE_INTERVAL_HOURS}h")

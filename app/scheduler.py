import logging
from datetime import date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.scrapers import scrape_all
from app.database import save_rate, get_today_rates

# Stores fetched via the paid scraping-API proxy — only worth fetching once/day
# (their rate is fixed for the day), to conserve credits.
PROXY_STORES = {"tanishq"}

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


async def run_scrape_job(skip_proxy: bool = False):
    logger.info("Starting scrape job...")
    # Skip paid-proxy stores we already have today (saves scraping-API credits).
    today_slugs = {r["store_slug"] for r in await get_today_rates() if r.get("gold_22k") is not None}
    skip = {s for s in PROXY_STORES if s in today_slugs}
    # User-triggered refreshes never spend credits on proxy stores — their rate
    # is fixed for the day and is refreshed by the once-daily scheduled job.
    if skip_proxy:
        skip |= PROXY_STORES
    if skip:
        logger.info(f"Skipping proxy stores: {', '.join(skip)}")
    rates = await scrape_all(skip=skip)
    saved = 0
    for rate in rates:
        if rate.gold_22k or rate.gold_24k or rate.gold_18k:
            await save_rate_with_history(rate)
            saved += 1
    logger.info(f"Scrape complete: {saved}/{len(rates)} stores saved")


def start_scheduler():
    # 9:20am IST = 03:50 UTC  |  4:10pm IST = 10:40 UTC
    for job_id, hour, minute in [("scrape_morning", 3, 50), ("scrape_afternoon", 10, 40)]:
        scheduler.add_job(run_scrape_job, "cron", hour=hour, minute=minute,
                          timezone="UTC", id=job_id, replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started: 9:20am IST and 4:10pm IST")

import asyncio
import logging
from datetime import date
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.config import BASE_DIR
from app.database import (
    init_db, get_today_rates, get_history, get_store_history,
    get_yesterday_rates, get_available_dates, save_rate,
)
from app.scrapers import scrape_store, SCRAPERS
from app.scheduler import start_scheduler, run_scrape_job, save_rate_with_history

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()

    async def _initial_scrape():
        try:
            if not await get_today_rates():
                logger.info("No data for today — running initial scrape")
                await run_scrape_job()
        except Exception as e:
            logger.warning(f"Initial scrape skipped: {e}")

    asyncio.create_task(_initial_scrape())
    logger.info("SONA gold tracker started")
    yield


app = FastAPI(title="SONA — Gold Rates", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/api/stores")
async def api_stores():
    return {"stores": list(SCRAPERS.values())}


@app.get("/api/rates/today")
async def api_today_rates():
    rates = await get_today_rates()
    yesterday = {r["store_slug"]: r for r in await get_yesterday_rates()}
    info = {s["slug"]: s for s in SCRAPERS.values()}
    present = set()

    for r in rates:
        y = yesterday.get(r["store_slug"])
        for p in ("22k", "24k", "18k"):
            key = f"gold_{p}"
            if y and r.get(key) is not None and y.get(key) is not None:
                r[f"change_{p}"] = round(r[key] - y[key], 2)
            else:
                r[f"change_{p}"] = None
        meta = info.get(r["store_slug"], {})
        r["logo"] = meta.get("logo", "")
        r["store_url"] = meta.get("url", r.get("source_url", ""))
        r["unavailable"] = False
        present.add(r["store_slug"])

    # Auto-scrape stores with no rate today (e.g. WAF-blocked from the cloud):
    # still list them as link-only so the user can open the store's own page.
    for s in SCRAPERS.values():
        if s.get("method") == "manual" or s["slug"] in present:
            continue
        rates.append({
            "store_name": s["name"], "store_slug": s["slug"],
            "gold_22k": None, "gold_24k": None, "gold_18k": None,
            "change_22k": None, "change_24k": None, "change_18k": None,
            "logo": s.get("logo", ""), "store_url": s.get("url", ""),
            "source_url": s.get("url", ""), "scraped_at": None,
            "unavailable": True,
        })

    return {"date": date.today().isoformat(), "rates": rates}


@app.get("/api/history")
async def api_history(days: int = 30):
    return {"days": days, "history": await get_history(days)}


@app.get("/api/history/{store_slug}")
async def api_store_history(store_slug: str, days: int = 30):
    return {"store": store_slug, "history": await get_store_history(store_slug, days)}


@app.get("/api/dates")
async def api_dates():
    return {"dates": await get_available_dates()}


@app.post("/api/scrape")
async def api_scrape():
    # User-triggered refresh: refresh the free direct stores only, never spend
    # scraping-API credits on the paid proxy stores (their rate is daily-fixed).
    await run_scrape_job(skip_proxy=True)
    return {"message": "Scrape completed"}


@app.post("/api/scrape/{store_slug}")
async def api_scrape_single(store_slug: str):
    rate = await scrape_store(store_slug)
    if not rate:
        raise HTTPException(404, "Store not found")
    if rate.gold_22k or rate.gold_24k or rate.gold_18k:
        await save_rate_with_history(rate)
    return {"store": rate.store_name, "gold_22k": rate.gold_22k,
            "gold_24k": rate.gold_24k, "gold_18k": rate.gold_18k}


def _num(v):
    """Coerce a submitted rate to float|None; reject anything non-numeric so the
    DB only ever holds numbers (a string rate would 500 the Postgres path and
    break sorting/rendering on SQLite)."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        raise HTTPException(400, "Rates must be numbers")


@app.post("/api/rates/manual")
async def api_manual(data: dict):
    for f in ("store_slug", "store_name"):
        if f not in data:
            raise HTTPException(400, f"Missing field: {f}")
    g22, g24, g18 = (_num(data.get(k)) for k in ("gold_22k", "gold_24k", "gold_18k"))
    if not any((g22, g24, g18)):
        raise HTTPException(400, "At least one rate required")
    await save_rate(
        str(data["store_name"])[:120], str(data["store_slug"])[:80],
        g22, g24, g18, str(data.get("source_url", "manual"))[:500],
    )
    return {"message": "Saved"}

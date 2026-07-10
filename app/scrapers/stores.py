import os
import logging
import asyncio
import re
import json
import html as _html
from datetime import datetime
import httpx
from curl_cffi import requests as cffi_requests
from .base import GoldRate, parse_price

logger = logging.getLogger(__name__)

# Optional scraping-API proxy, used on the cloud where Tanishq's WAF blocks
# datacenter IPs. ScrapingAnt has a permanent free tier (10k credits/mo) with
# residential + India-geo proxies. When no key is set (e.g. a local residential
# IP), Tanishq is fetched directly with TLS impersonation.
SCRAPINGANT_API_KEY = os.environ.get("SCRAPINGANT_API_KEY", "").strip()
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "").strip()  # ScraperAPI fallback


def _proxy_get(url: str, timeout: int = 70):
    """Fetch a URL through a residential/India scraping-API if a key is set,
    else fetch directly with a browser-impersonating client."""
    if SCRAPINGANT_API_KEY:
        return httpx.get("https://api.scrapingant.com/v2/general", params={
            "url": url,
            "x-api-key": SCRAPINGANT_API_KEY,
            "proxy_type": "residential",   # beats the datacenter-IP block
            "proxy_country": "IN",         # India geo
            "browser": "false",            # static HTML → 25 credits, no JS render
        }, timeout=timeout, follow_redirects=True)
    if SCRAPER_API_KEY:
        return httpx.get("https://api.scraperapi.com/", params={
            "api_key": SCRAPER_API_KEY, "url": url, "country_code": "in",
        }, timeout=timeout, follow_redirects=True)
    return cffi_requests.Session(impersonate="chrome131").get(url, timeout=15)


def _favicon(domain: str) -> str:
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=64"


# ── Region-verified store list ──
# Every auto-scraped store has a confirmed physical showroom in at least one of
# Delhi / Moradabad / Bareilly. Method "manual" = famous local jeweller with no
# scrapable online rate (added by the user via the form).
STORE_CONFIGS = [
    # ---- auto-scraped (verified region + working source) ----
    {"name": "Tanishq", "slug": "tanishq", "method": "tanishq",
     "url": "https://www.tanishq.co.in/gold-rate.html", "logo": _favicon("tanishq.co.in"),
     "cities": ["Delhi", "Moradabad", "Bareilly"]},
    {"name": "Malabar Gold", "slug": "malabar-gold", "method": "malabar",
     "url": "https://www.malabargoldanddiamonds.com/in/pan-india/en/live-gold-rate.html",
     "logo": "https://www.malabargoldanddiamonds.com/etc.clientlibs/mgdsite/clientlibs/clientlib-react/resources/logo192.png",
     "cities": ["Delhi", "Bareilly"]},
    {"name": "Kalyan Jewellers", "slug": "kalyan-jewellers", "method": "kalyan",
     "url": "https://www.kalyanjewellers.net/gold-rate/Gold-Rate-Today", "logo": _favicon("kalyanjewellers.net"),
     "cities": ["Delhi", "Moradabad", "Bareilly"]},
    {"name": "Senco Gold", "slug": "senco-gold", "method": "senco",
     "url": "https://sencogoldanddiamonds.com/gold-price-calculator", "logo": _favicon("sencogoldanddiamonds.com"),
     "cities": ["Delhi", "Ghaziabad", "Noida"]},
    {"name": "CaratLane", "slug": "caratlane", "method": "caratlane",
     "url": "https://www.caratlane.com/gold-rate/delhi/new-delhi-gold-rate-today", "logo": _favicon("caratlane.com"),
     "cities": ["Delhi", "Moradabad", "Bareilly"]},
    {"name": "Candere", "slug": "candere", "method": "candere",
     "url": "https://www.candere.com/gold-rate-today/delhi", "logo": _favicon("candere.com"),
     "cities": ["Delhi", "Ghaziabad"]},

    # ---- manual-only (famous local, no online rate) ----
    {"name": "PC Jeweller", "slug": "pc-jeweller", "method": "manual",
     "url": "https://www.pcjeweller.com/", "logo": _favicon("pcjeweller.com"),
     "cities": ["Delhi", "Bareilly"]},
    {"name": "Reliance Jewels", "slug": "reliance-jewels", "method": "manual",
     "url": "https://www.reliancejewels.com/", "logo": _favicon("reliancejewels.com"),
     "cities": ["Delhi", "Moradabad", "Bareilly"]},
    {"name": "TBZ The Original", "slug": "tbz", "method": "manual",
     "url": "https://www.tbztheoriginal.com/", "logo": _favicon("tbztheoriginal.com"),
     "cities": ["Delhi"]},
    {"name": "Lala Jugal Kishore (Moradabad)", "slug": "lala-jugal-kishore", "method": "manual",
     "url": "", "logo": "", "cities": ["Moradabad"]},
    {"name": "Harsahaimal Shiamlal (Moradabad)", "slug": "hsj-moradabad", "method": "manual",
     "url": "", "logo": "", "cities": ["Moradabad", "Bareilly"]},
    {"name": "Ram Kumar Sarraf (Bareilly)", "slug": "ram-kumar-sarraf", "method": "manual",
     "url": "", "logo": "", "cities": ["Bareilly"]},
    {"name": "PP Jewellers (Karol Bagh)", "slug": "pp-jewellers", "method": "manual",
     "url": "https://www.ppjewellers.com/", "logo": _favicon("ppjewellers.com"), "cities": ["Delhi"]},
    {"name": "Hazoorilal Legacy", "slug": "hazoorilal", "method": "manual",
     "url": "https://www.hazoorilallegacy.com/", "logo": _favicon("hazoorilallegacy.com"), "cities": ["Delhi"]},
]

SCRAPERS = {s["slug"]: s for s in STORE_CONFIGS}


def _make_rate(config: dict) -> GoldRate:
    return GoldRate(store_name=config["name"], store_slug=config["slug"],
                    source_url=config["url"], logo=config.get("logo", ""))


def _sanitize(rate: GoldRate) -> GoldRate:
    """Drop implausible values. Indian gold rates are tightly proportional to purity
    (24K/22K ≈ 999/916 = 1.091, 18K/22K ≈ 750/916 = 0.819)."""
    def ok(v, lo, hi):
        return v is not None and lo <= v <= hi
    if not ok(rate.gold_22k, 8000, 20000):
        rate.gold_22k = None
    if not ok(rate.gold_24k, 9000, 22000):
        rate.gold_24k = None
    if not ok(rate.gold_18k, 6500, 16000):
        rate.gold_18k = None
    # Cross-purity consistency vs 22K anchor (±4%)
    if rate.gold_22k:
        if rate.gold_24k and not (1.05 <= rate.gold_24k / rate.gold_22k <= 1.14):
            rate.gold_24k = None
        if rate.gold_18k and not (0.78 <= rate.gold_18k / rate.gold_22k <= 0.86):
            rate.gold_18k = None
    return rate


def _inr(text) -> float | None:
    if text is None:
        return None
    s = str(text)
    if "n/a" in s.lower():
        return None
    m = re.search(r"[\d,]+(?:\.\d+)?", s)
    return parse_price(m.group(0)) if m else None


# ═══════════════ Tanishq (curl_cffi + 30d history) ═══════════════
# Tanishq's Cloudflare WAF blocks datacenter IPs (e.g. cloud hosts), so we fall
# back to Mia by Tanishq — same Titan group, identical rate + history, different infra.
_TANISHQ_MIA = "https://www.miabytanishq.com/en_IN/gold-rate-today"


def _parse_tanishq_html(html: str, rate: GoldRate) -> bool:
    m = re.search(r'id="goldRateValues"[^>]*?value="(.*?)"\s*/?>', html, re.DOTALL)
    if m:
        try:
            rows = json.loads(_html.unescape(m.group(1))).get("GetDailyMetalRates", [])
            hist = []
            for row in rows:
                try:
                    d = datetime.strptime(row["Date"], "%d-%m-%Y").date().isoformat()
                except Exception:
                    continue
                hist.append({"date": d, "gold_22k": parse_price(row.get("GoldRate22KT")),
                             "gold_24k": parse_price(row.get("GoldRate24KT")),
                             "gold_18k": parse_price(row.get("GoldRate18KT"))})
            if hist:
                hist.sort(key=lambda x: x["date"])
                latest = hist[-1]
                rate.gold_22k, rate.gold_24k, rate.gold_18k = latest["gold_22k"], latest["gold_24k"], latest["gold_18k"]
                rate.history = hist
                return True
        except json.JSONDecodeError:
            pass
    for kt, attr in (("22k", "22kt"), ("24k", "24kt"), ("18k", "18kt")):
        mm = re.search(rf'data-goldrate{attr}="(\d+)"', html)
        if mm:
            setattr(rate, f"gold_{kt}", float(mm.group(1)))
    return rate.gold_22k is not None


def _s_tanishq(cfg):
    rate = _make_rate(cfg)
    proxied = bool(SCRAPINGANT_API_KEY or SCRAPER_API_KEY)
    # When proxied (cloud), one residential request to the main URL succeeds — do
    # NOT also fetch Mia (it would double the paid credits). Mia is only a free
    # fallback for the direct/residential path.
    urls = [cfg["url"]] if proxied else [cfg["url"], _TANISHQ_MIA]
    for url in urls:
        try:
            r = _proxy_get(url)
            if r.status_code == 200 and _parse_tanishq_html(r.text, rate):
                via = "scraping-API" if proxied else ("Mia fallback" if "mia" in url else "direct")
                logger.info(f"Tanishq: via {via}")
                return rate
        except Exception as e:
            logger.warning(f"Tanishq attempt {url.split('//')[1][:25]}: {e}")
    return rate


# ═══════════════ Malabar (GraphQL) ═══════════════
def _s_malabar(cfg):
    rate = _make_rate(cfg)
    q = "query getMetalRate($filter: MetalRateFilterInput){getMetalRate(filter:$filter){items{purity rate}}}"
    s = cffi_requests.Session(impersonate="chrome131")
    d = s.get("https://www.malabargoldanddiamonds.com/graphql-magento",
              params={"query": q, "variables": json.dumps({"filter": {"metal_type": "gold", "country": "India"}})},
              headers={"Referer": cfg["url"]}, timeout=15).json()
    for it in d.get("data", {}).get("getMetalRate", {}).get("items", []):
        p = (it.get("purity") or "").lower()
        v = parse_price(it.get("rate"))
        if p == "22k": rate.gold_22k = v
        elif p == "24k": rate.gold_24k = v
        elif p == "18k": rate.gold_18k = v
    return rate


# ═══════════════ Kalyan (AJAX via curl_cffi) ═══════════════
def _s_kalyan(cfg):
    rate = _make_rate(cfg)
    s = cffi_requests.Session(impersonate="chrome131")
    H = {"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest",
         "Referer": cfg["url"], "Origin": "https://www.kalyanjewellers.net"}
    s.get(cfg["url"], timeout=15)
    # India(1) / Delhi(4) / Dwarka(17)
    d = s.post("https://www.kalyanjewellers.net/kalyan_gold_rates/ajax/get_rate",
               data="countryId=1&stateId=4&cityId=17", headers=H, timeout=15).json()
    rate.gold_22k = _inr(d.get("today_22k"))
    rate.gold_24k = _inr(d.get("today_24k"))
    rate.gold_18k = _inr(d.get("today_18k"))
    if not rate.gold_22k:
        mm = re.search(r"22\s*kt\s*:?\s*(?:</label>)?\s*INR\s*([\d,.]+)", d.get("html", ""), re.IGNORECASE)
        if mm:
            rate.gold_22k = parse_price(mm.group(1))
    return rate


# ═══════════════ Senco (calculator API) ═══════════════
def _s_senco(cfg):
    rate = _make_rate(cfg)
    s = cffi_requests.Session(impersonate="chrome131")
    d = s.get("https://api.sencogoldanddiamonds.com/calculator/list",
              headers={"Client-ID": "63866e9b-b9b8-4186-ac1c-b0855390f4df",
                       "Origin": "https://sencogoldanddiamonds.com", "Accept": "application/json"}, timeout=15).json()
    gold = d.get("GOLD", [])
    def pick(name):
        return next((x.get("price") for x in gold if x.get("name") == name), None)
    rate.gold_22k = parse_price(pick("91.66"))
    rate.gold_24k = parse_price(pick("99.99"))
    rate.gold_18k = parse_price(pick("75.00"))
    return rate


# ═══════════════ CaratLane (per-city HTML) ═══════════════
def _s_caratlane(cfg):
    rate = _make_rate(cfg)
    s = cffi_requests.Session(impersonate="chrome131")
    html = s.get(cfg["url"], timeout=15).text
    for kt in ("22", "24", "18"):
        mm = re.search(rf'"rate_{kt}kt"\s*:\s*(\d+)', html)
        if mm:
            setattr(rate, f"gold_{kt}k", float(mm.group(1)))
    return rate


# ═══════════════ Candere (HTML data-rate, with retry) ═══════════════
def _s_candere(cfg):
    rate = _make_rate(cfg)
    last = None
    for _ in range(3):
        try:
            s = cffi_requests.Session(impersonate="chrome131")
            html = s.get(cfg["url"], timeout=20).text
            for kt in ("22", "24", "18"):
                mm = re.search(rf'id="goldPrice{kt}k"[^>]*data-rate="(\d+)"', html)
                if mm:
                    setattr(rate, f"gold_{kt}k", float(mm.group(1)))
            if rate.gold_22k:
                return rate
        except Exception as e:
            last = e
    if last:
        logger.warning(f"Candere retries exhausted: {last}")
    return rate


_FUNCS = {
    "tanishq": _s_tanishq, "malabar": _s_malabar, "kalyan": _s_kalyan,
    "senco": _s_senco, "caratlane": _s_caratlane, "candere": _s_candere,
}


async def _run(cfg) -> GoldRate:
    fn = _FUNCS.get(cfg["method"])
    if not fn:
        return _make_rate(cfg)
    try:
        rate = await asyncio.to_thread(fn, cfg)
        rate = _sanitize(rate)
        n = len(rate.history) if rate.history else 0
        logger.info(f"{cfg['name']}: 22K={rate.gold_22k} 24K={rate.gold_24k} 18K={rate.gold_18k}"
                    + (f" (+{n}d history)" if n else ""))
        return rate
    except Exception as e:
        logger.error(f"{cfg['name']} scrape failed: {e}")
        return _make_rate(cfg)


# ─────────── Public API ───────────
async def scrape_store(slug: str) -> GoldRate | None:
    cfg = SCRAPERS.get(slug)
    if not cfg or cfg["method"] == "manual":
        return None
    return await _run(cfg)


async def scrape_all(skip: set | None = None) -> list[GoldRate]:
    skip = skip or set()
    targets = [c for c in STORE_CONFIGS if c["method"] != "manual" and c["slug"] not in skip]
    return await asyncio.gather(*[_run(c) for c in targets])

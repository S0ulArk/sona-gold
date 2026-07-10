# SONA — Live Gold Rates

Compare today's **22K / 24K / 18K** gold rates across India's trusted jewellers, side by side.
Built for buyers in Delhi & western Uttar Pradesh (Moradabad, Bareilly) — every listed jeweller has a
physical showroom in the region.

## Features
- Live rates scraped directly from each jeweller's official site (no third-party aggregator)
- 22K / 24K / 18K toggle, "best price" highlighting, "vs best" savings per store
- Market-trend chart (per-day median across stores) + per-store history lines
- Editorial mono-yellow UI, mobile-first; auto-refreshes twice daily (9:20am & 4:10pm IST)
- Manual-rate API (`POST /api/rates/manual`) for famous local jewellers with no online rate

## Run locally
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py            # → http://localhost:8000  (uses a local SQLite file)
```

## History note
Rates are stored in a local SQLite file. On Render's **free** plan the disk is ephemeral
(wiped on every deploy and after ~15 min idle), so accumulated per-store history resets
there — but the **market-trend chart still works**, because Tanishq ships its own 30-day
history that's re-read on each start. To make every jeweller's history persist and build
up over 30 days, point the storage layer (`app/database.py`) at an external database.

## Deploy
One-click via `render.yaml` (Render Blueprint). Start command:
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```
`DATABASE_URL` is declared in `render.yaml` with `sync: false` — set its value in the dashboard.

## Stack
FastAPI · curl_cffi / httpx scrapers · SQLite · APScheduler · vanilla JS + Chart.js
(editorial mono-yellow UI, no build step)

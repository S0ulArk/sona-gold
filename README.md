# SONA — Live Gold Rates

Compare today's **22K / 24K / 18K** gold rates across India's trusted jewellers, side by side.
Built for buyers in Delhi & western Uttar Pradesh (Moradabad, Bareilly) — every listed jeweller has a
physical showroom in the region.

## Features
- Live rates scraped directly from each jeweller's official site (no third-party aggregator)
- 22K / 24K / 18K toggle, "best price" highlighting, per-10g view
- 30-day price-history chart
- Mobile-first design; auto-refreshes every 4 hours
- Add famous local jewellers manually (e.g. Lala Jugal Kishore, Moradabad)

## Run locally
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python run.py            # → http://localhost:8000
```

## Deploy
One-click via `render.yaml` (Render Blueprint). Start command:
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Stack
FastAPI · curl_cffi / httpx scrapers · SQLite · APScheduler · vanilla JS + Chart.js

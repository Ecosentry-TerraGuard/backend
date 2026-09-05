# TerraGuard Backend

Backend for TerraGuard — AI-powered landslide early warning system, built for SIH26001.

## Quickstart

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open **http://localhost:8000/docs** — interactive API docs, try every endpoint from the browser.

## Get demo data flowing immediately

```bash
curl -X POST "http://localhost:8000/api/v1/seed/demo?days_of_history=3"
```

This creates 3 mock zones, 6 sensor nodes, several days of readings/rainfall, and a run of risk predictions — so the frontend and ML teammates have real data to build against right away, without waiting on hardware or a trained model.

To wipe and re-seed cleanly: add `&reset=true` to the URL above.

## Project structure

```
app/
  main.py          - FastAPI app, wires everything together
  database.py      - DB connection (SQLite by default, Postgres via DATABASE_URL env var)
  models.py        - SQLAlchemy tables (zones, sensor_nodes, sensor_readings, rainfall_data, risk_predictions, alert_logs)
  schemas.py        - Pydantic request/response shapes (this doubles as the API contract)
  ml_client.py     - predict_risk() — the ONE function the ML team needs to swap in their real model
  alerts.py        - dispatch_alert() — swap in real Twilio/SMTP here later
  routers/
    zones.py       - create/list zones
    sensors.py     - register nodes, push readings (the ESP32 endpoint), read latest/history
    risk.py        - trigger predictions, read latest/history
    alerts.py      - manually trigger alerts, view alert log
    seed.py        - mock data generator (dev only)
```

See `API_CONTRACT.md` for the full endpoint reference to hand to your frontend and ML teammates.

## Switching to PostgreSQL (only if you need it)

```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/terraguard"
pip install psycopg2-binary
```
No code changes needed — `app/database.py` reads this env var.

## What's intentionally simple (for the 10-day timeline)

- No auth/API keys on any endpoint — fine for a hackathon demo, not for production.
- No Alembic migrations — tables are created automatically on startup (`Base.metadata.create_all`). Fine as long as you don't need to preserve data across schema changes; if a table's shape changes mid-hackathon, easiest fix is deleting `terraguard.db` and re-seeding.
- Alerts are simulated (logged, not actually sent) by default. Flip `REAL_ALERTS_ENABLED` in `app/alerts.py` and fill in Twilio/SMTP credentials if you have time.
- The seed endpoint (`/api/v1/seed/demo`) has no safety rails — don't ship it to a real deployment, but it's exactly what you want for parallel development and demo resets.

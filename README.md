# TerraGuard Backend

Backend for TerraGuard — AI-powered landslide early warning system, built for SIH26001.

## Overview

This is the backend service that serves as the central integration layer between:
- Frontend dashboard (React/Vite)
- ML model (Random Forest trained on soil moisture, rainfall, slope, NDVI, and landslide density)
- IoT/ESP32 sensor nodes
- Alerting systems (Twilio/SMTP - simulated in demo)

The backend provides RESTful APIs for all system components and handles data persistence, risk prediction orchestration, and alert generation.

## Key Features

- **RESTful API**: Complete API contract defined in `API_CONTRACT.md`
- **ML Model Integration**: Isolated `ml_client.py` with `predict_risk()` function for seamless ML team integration
- **Automatic Schema Creation**: SQLite database auto-created on startup (delete `terraguard.db` to reset schema)
- **Mock Data Generation**: `/api/v1/seed/demo` endpoint for instant demo data
- **CORS Enabled**: Configured for frontend development on different ports
- **Health Check Endpoint**: Simple liveness check at `/`
- **Risk Score Convention**: Backend uses 0.0-1.0 range, frontend converts to 0-100 for display
- **Live Safety Overrides**: Tilt angle used as live escalation check (not in ML model)

## Project Structure

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

## API Contract

See `API_CONTRACT.md` for the complete endpoint reference to hand to your frontend and ML teammates.

### Critical Integration Points

1. **ML Team Integration Point**: 
   - Only file to modify: `app/ml_client.py`
   - Only function to implement: `predict_risk(soil_moisture, rainfall_mm, slope, ndvi, landslide_density)`
   - Returns: `(risk_score: float 0.0-1.0, risk_level: RiskLevel)`
   - Helper function `score_to_level()` already provided for bucketing

2. **Frontend Integration**:
   - Frontend expects risk_score in 0.0-1.0 range (converts to 0-100 for display)
   - All timestamps in ISO-8601 UTC
   - CORS enabled for localhost:3000/dev server testing

3. **IoT/ESP32 Integration**:
   - POST `/api/v1/readings` for sensor data ingestion
   - POST `/api/v1/nodes` for device registration
   - All sensor fields optional (send available data)

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

This creates 4 mock zones, 8 sensor nodes, several days of readings/rainfall, and a run of risk predictions — so the frontend and ML teammates have real data to build against right away, without waiting on hardware or a trained model.

To wipe and re-seed cleanly: add `&reset=true` to the URL above.

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

## Data Flow

1. **Sensor Data**: ESP32 nodes → POST `/api/v1/readings` → stored in `sensor_readings` table
2. **Risk Prediction**: Frontend or manual trigger → POST `/api/v1/zones/{zone_id}/risk/predict` → calls `ml_client.predict_risk()` → stores result in `risk_predictions` table
3. **Alert Generation**: If risk_level = High → automatic alert created in `alert_logs` table
4. **Frontend Consumption**: 
   - GET `/api/v1/zones` → zone list with basic info
   - GET `/api/v1/zones/{zone_id}/readings/latest` → current sensor readings per node
   - GET `/api/v1/zones/{zone_id}/risk/latest` → current risk score (0.0-1.0) and level
   - GET `/api/v1/alerts?zone_id={id}` → alert log

## Development Notes

- When backend shape changes, delete `terraguard.db` and re-seed to update schema
- The `ml_client.py` file is designed as an integration seam — ML team only needs to replace the mock implementation with their real model call
- All API calls include proper error handling with FastAPI's standard error shape
- Timestamp handling uses ISO-8601 UTC throughout the system
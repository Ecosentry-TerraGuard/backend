# TerraGuard API Contract (v0.1)

Base URL (local dev): `http://localhost:8000`
Interactive docs (try every endpoint in-browser): `http://localhost:8000/docs`

All request/response bodies are JSON. All timestamps are ISO-8601 UTC.

---

## For the Frontend teammate

### List zones
`GET /api/v1/zones`
```json
[{ "id": 1, "name": "Sohra Ridge", "description": "...", "latitude": 25.28, "longitude": 91.72, "created_at": "..." }]
```

### Latest sensor readings for a zone (one per node)
`GET /api/v1/zones/{zone_id}/readings/latest`
```json
[{ "id": 25, "node_id": 1, "timestamp": "...", "soil_moisture": 31.6, "tilt_angle": 3.79, "vibration": 0.12, "battery_voltage": 3.73 }]
```

### Historical sensor readings for a zone
`GET /api/v1/zones/{zone_id}/readings/history?hours=24`
Same shape as above, array of all readings across all nodes in that zone in the lookback window.

### Latest risk score for a zone
`GET /api/v1/zones/{zone_id}/risk/latest`
```json
{ "id": 9, "zone_id": 1, "timestamp": "...", "risk_score": 0.136, "risk_level": "Low", "model_version": "mock-v0-seed", "input_features": {...} }
```
`risk_level` is always one of `"Low" | "Medium" | "High"`.

### Risk history for a zone (for trend charts)
`GET /api/v1/zones/{zone_id}/risk/history?hours=24`
Array of the same shape as above.

### Alert log
`GET /api/v1/alerts?zone_id=1` (zone_id optional — omit for all zones)
```json
[{ "id": 1, "zone_id": 1, "risk_prediction_id": 28, "triggered_at": "...", "alert_type": "simulated", "recipient": null, "message": "HIGH landslide risk detected in zone 'Sohra Ridge' (score=0.964).", "status": "simulated" }]
```

---

## For the ML teammates

You don't need to touch the API at all. Everything you need is **one function** in `app/ml_client.py`:

```python
def predict_risk(soil_moisture, tilt_angle, vibration, rainfall_mm) -> tuple[float, RiskLevel]:
    ...
```

- Inputs: four floats (any may be `None` if that sensor/data isn't available).
- Output: `(risk_score, risk_level)` — `risk_score` is a float 0.0–1.0, `risk_level` is `RiskLevel.LOW / MEDIUM / HIGH` (use the `score_to_level()` helper already in that file to bucket your model's raw score).

Replace the mock body with your real model call (see the comment in the file for the exact swap-in pattern with `joblib`). Nothing else in the backend needs to change — the backend calls this function every time `POST /api/v1/zones/{zone_id}/risk/predict` is hit.

---

## For the IoT/ESP32 teammate

### Push a sensor reading
`POST /api/v1/readings`
```json
{
  "node_identifier": "ESP32-SOHRAR-01",
  "soil_moisture": 42.5,
  "tilt_angle": 4.1,
  "vibration": 0.8,
  "battery_voltage": 3.9
}
```
- `node_identifier` must already be registered (see below) — it's how we know which physical device sent this.
- All sensor fields are optional — send whatever your firmware has (e.g. omit `battery_voltage` if you're not tracking it).
- `timestamp` is optional — omit it and the server stamps it on arrival (recommended, avoids ESP32 clock-drift issues).

### Register a new node (do this once per physical device)
`POST /api/v1/nodes`
```json
{ "node_identifier": "ESP32-SOHRAR-01", "name": "Sohra Ridge Node 1", "zone_id": 1, "latitude": 25.28, "longitude": 91.73 }
```

---

## Triggering things manually (for demo/testing)

### Force a risk prediction (bypasses waiting for real sensor data)
`POST /api/v1/zones/{zone_id}/risk/predict`
```json
{ "soil_moisture": 95, "tilt_angle": 40, "vibration": 9, "rainfall_mm": 95 }
```
Body is fully optional — pass `{}` and it uses the zone's latest stored readings/rainfall instead. If the result is `"High"`, an alert fires automatically.

### Manually fire an alert (for the live demo)
`POST /api/v1/alerts/trigger`
```json
{ "zone_id": 1, "message": "Optional custom message", "recipient": "optional" }
```

### Seed/reset mock demo data (dev only)
`POST /api/v1/seed/demo?days_of_history=3&reset=true`
Populates 3 mock zones, 6 nodes, several days of readings/rainfall, and a run of risk predictions. Use `reset=true` to wipe and re-seed cleanly. **Remove or lock this endpoint down before any real deployment.**

---

## Error shape

All errors return FastAPI's standard shape:
```json
{ "detail": "human-readable message" }
```
with the appropriate HTTP status code (404 not found, 409 conflict, 422 validation error).

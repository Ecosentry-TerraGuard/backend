"""
routers/seed.py — generates realistic mock data so the frontend and ML
teammates can integrate against your API before real ESP32 hardware or
a trained model exist.

Call POST /api/v1/seed/demo once after starting the server. It:
  1. Creates a few zones (mock NER hillside locations)
  2. Registers a couple of sensor nodes per zone
  3. Generates several days of readings + rainfall history
  4. Runs mock risk predictions across that history
  5. Fires a couple of alerts so the alert log isn't empty

This is a DEV-ONLY convenience endpoint — you'd remove or lock it down
before any real deployment, but for a 10-day hackathon it's exactly
what you need to keep three teams unblocked in parallel.
"""

import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.ml_client import predict_risk
from app.alerts import dispatch_alert

router = APIRouter(prefix="/api/v1/seed", tags=["seed (dev only)"])

MOCK_ZONES = [
    {"name": "Sohra (Cherrapunji), Meghalaya", "description": "Steep hillside sector near Sohra (Cherrapunji)", "latitude": 25.2840, "longitude": 91.7273, "slope": 25.0, "ndvi": 0.8, "landslide_density": 0.6},
    {"name": "Mawsynram, Meghalaya", "description": "Terraced slope, historically prone to slippage", "latitude": 25.2971, "longitude": 91.5809, "slope": 20.0, "ndvi": 0.75, "landslide_density": 0.5},
    {"name": "Aizawl, Mizoram", "description": "River-adjacent slope with loose sediment", "latitude": 23.7271, "longitude": 92.7176, "slope": 30.0, "ndvi": 0.6, "landslide_density": 0.7},
    {"name": "NH6 Corridor - Shillong Approach", "description": "Steep hillside sector near Shillong approach on NH6", "latitude": 25.5788, "longitude": 91.8933, "slope": 15.0, "ndvi": 0.5, "landslide_density": 0.3},
]


@router.post("/demo", status_code=201)
def seed_demo_data(
    days_of_history: int = 3,
    reset: bool = False,
    db: Session = Depends(get_db),
):
    """
    Populate the database with mock data.

    Query params:
        days_of_history: how many days of readings/rainfall/predictions
                          to backfill (default 3 — keep it small for a
                          fast demo reset)
        reset: if true, wipes existing zones/nodes/readings/predictions/
               alerts first (rainfall included) for a clean re-seed
    """
    if reset:
        db.query(models.AlertLog).delete()
        db.query(models.RiskPrediction).delete()
        db.query(models.SensorReading).delete()
        db.query(models.RainfallData).delete()
        db.query(models.SensorNode).delete()
        db.query(models.Zone).delete()
        db.commit()

    created_zones = []
    for zone_data in MOCK_ZONES:
        existing = db.query(models.Zone).filter(models.Zone.name == zone_data["name"]).first()
        if existing:
            created_zones.append(existing)
            continue
        zone = models.Zone(**zone_data)
        db.add(zone)
        db.commit()
        db.refresh(zone)
        created_zones.append(zone)

    now = datetime.now(timezone.utc)
    all_nodes = []

    for zone in created_zones:
        # Two sensor nodes per zone.
        for i in range(1, 3):
            node_identifier = f"ESP32-{zone.name.replace(' ', '').upper()[:6]}-{i:02d}"
            existing_node = db.query(models.SensorNode).filter(
                models.SensorNode.node_identifier == node_identifier
            ).first()
            if existing_node:
                all_nodes.append(existing_node)
                continue
            node = models.SensorNode(
                node_identifier=node_identifier,
                name=f"{zone.name} Node {i}",
                zone_id=zone.id,
                latitude=zone.latitude + random.uniform(-0.01, 0.01),
                longitude=zone.longitude + random.uniform(-0.01, 0.01),
                status=models.NodeStatus.ACTIVE,
            )
            db.add(node)
            db.commit()
            db.refresh(node)
            all_nodes.append(node)

        # Rainfall history: one figure per day, with a couple of "storm days"
        # to make risk scores vary interestingly in the demo.
        for d in range(days_of_history, -1, -1):
            date = now - timedelta(days=d)
            is_storm_day = random.random() < 0.25
            rainfall_mm = random.uniform(40, 90) if is_storm_day else random.uniform(0, 15)
            db.add(models.RainfallData(
                zone_id=zone.id,
                date=date,
                rainfall_mm=round(rainfall_mm, 1),
                source="public_dataset_mock",
            ))
        db.commit()

    # Readings every ~2 hours across the history window, per node.
    hours_span = days_of_history * 24
    for node in all_nodes:
        for h in range(hours_span, -1, -2):
            ts = now - timedelta(hours=h)
            # Drift soil moisture/tilt/vibration slightly upward as we
            # approach "now" on ~1/3 of nodes, to simulate a developing
            # risk scenario worth showing in the demo.
            drift = 0.0
            if node.id % 3 == 0:
                drift = (hours_span - h) / hours_span * 25  # ramps up over time

            reading = models.SensorReading(
                node_id=node.id,
                timestamp=ts,
                soil_moisture=round(random.uniform(20, 45) + drift, 1),
                tilt_angle=round(random.uniform(0.5, 5) + drift / 8, 2),
                vibration=round(random.uniform(0.1, 1.5) + drift / 20, 2),
                battery_voltage=round(random.uniform(3.6, 4.2), 2),
            )
            db.add(reading)
        node.last_seen_at = now
    db.commit()

    # Run mock risk predictions per zone across a few points in the history.
    alerts_created = 0
    for zone in created_zones:
        zone_node_ids = [n.id for n in zone.sensor_nodes]
        for h in range(hours_span, -1, -6):
            ts = now - timedelta(hours=h)
            reading = (
                db.query(models.SensorReading)
                .filter(models.SensorReading.node_id.in_(zone_node_ids))
                .filter(models.SensorReading.timestamp <= ts)
                .order_by(models.SensorReading.timestamp.desc())
                .first()
            )
            rainfall = (
                db.query(models.RainfallData)
                .filter(models.RainfallData.zone_id == zone.id)
                .filter(models.RainfallData.date <= ts)
                .order_by(models.RainfallData.date.desc())
                .first()
            )
            soil_moisture = reading.soil_moisture if reading else None
            tilt_angle = reading.tilt_angle if reading else None
            vibration = reading.vibration if reading else None
            rainfall_mm = rainfall.rainfall_mm if rainfall else None

            # Call predict_risk with live + static features (tilt and vibration are NOT model inputs)
            score, level = predict_risk(
                soil_moisture if soil_moisture is not None else 0.0,
                rainfall_mm if rainfall_mm is not None else 0.0,
                zone.slope if zone.slope is not None else 0.0,
                zone.ndvi if zone.ndvi is not None else 0.0,
                zone.landslide_density if zone.landslide_density is not None else 0.0,
            )

            # Check for tilt escalation as a safety override
            tilt_escalation_applied = False
            if tilt_angle is not None and level in (models.RiskLevel.MEDIUM, models.RiskLevel.HIGH):
                # Use a reasonable baseline - for demo, assume baseline is 2 degrees
                # (normal resting tilt for a stable slope)
                tilt_baseline = 2.0
                from app.ml_client import check_tilt_escalation
                if check_tilt_escalation(tilt_angle, tilt_baseline):
                    # Escalate risk level by one step, but not above HIGH
                    if level == models.RiskLevel.MEDIUM:
                        level = models.RiskLevel.HIGH
                    elif level == models.RiskLevel.LOW:
                        level = models.RiskLevel.MEDIUM
                    # Don't escalate if already HIGH
                    tilt_escalation_applied = True

            prediction = models.RiskPrediction(
                zone_id=zone.id,
                timestamp=ts,
                risk_score=score,
                risk_level=level,
                model_version="mock-v0-seed",
                input_features={
                    "soil_moisture": soil_moisture,
                    "rainfall_mm": rainfall_mm,
                    "slope": zone.slope,
                    "ndvi": zone.ndvi,
                    "landslide_density": zone.landslide_density,
                    "tilt_angle": tilt_angle,
                    "vibration": vibration,
                    "tilt_escalation_applied": tilt_escalation_applied,
                },
            )
            db.add(prediction)
            db.commit()
            db.refresh(prediction)

            if level == models.RiskLevel.HIGH:
                dispatch_alert(
                    db=db,
                    zone_id=zone.id,
                    message=f"HIGH landslide risk detected in zone '{zone.name}' (score={score}).",
                    risk_prediction_id=prediction.id,
                    alert_type="simulated",
                )
                alerts_created += 1

    return {
        "status": "ok",
        "zones_created": len(created_zones),
        "nodes_created": len(all_nodes),
        "days_of_history": days_of_history,
        "alerts_created": alerts_created,
        "message": "Demo data seeded. Try GET /api/v1/zones to see results.",
    }

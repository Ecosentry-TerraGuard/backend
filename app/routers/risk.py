"""
routers/risk.py — trigger a risk prediction and read prediction history.

The trigger endpoint is where the ML model gets called. Right now it
calls the mock in ml_client.py; once the real model is ready, only
ml_client.py changes, not this file.

This is also where alerts get fired: if a prediction comes back HIGH,
we automatically log an alert.
"""

from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.ml_client import predict_risk
from app.alerts import dispatch_alert

router = APIRouter(prefix="/api/v1/zones", tags=["risk"])


@router.post("/{zone_id}/risk/predict", response_model=schemas.RiskPredictionOut, status_code=201)
def trigger_prediction(
    zone_id: int,
    payload: schemas.RiskPredictTrigger,
    db: Session = Depends(get_db),
):
    """
    Runs a risk prediction for a zone and stores the result.

    You can call this two ways:
    1. Pass soil_moisture/tilt_angle/vibration/rainfall_mm explicitly in
       the body (useful for testing, or for the ML/demo teammate to
       force a specific scenario).
    2. Pass an empty body {} — the endpoint will pull the zone's most
       recent sensor reading and rainfall figure automatically. This is
       what you'd wire up to run on a schedule (e.g. every 15 min) once
       real sensors are reporting.
    """
    zone = db.query(models.Zone).filter(models.Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    soil_moisture = payload.soil_moisture
    tilt_angle = payload.tilt_angle
    vibration = payload.vibration
    rainfall_mm = payload.rainfall_mm

    # Auto-fill from latest data if not explicitly provided.
    if soil_moisture is None or tilt_angle is None or vibration is None:
        node_ids = [n.id for n in zone.sensor_nodes]
        if node_ids:
            latest_reading = (
                db.query(models.SensorReading)
                .filter(models.SensorReading.node_id.in_(node_ids))
                .order_by(models.SensorReading.timestamp.desc())
                .first()
            )
            if latest_reading:
                soil_moisture = soil_moisture if soil_moisture is not None else latest_reading.soil_moisture
                tilt_angle = tilt_angle if tilt_angle is not None else latest_reading.tilt_angle
                vibration = vibration if vibration is not None else latest_reading.vibration

    if rainfall_mm is None:
        latest_rainfall = (
            db.query(models.RainfallData)
            .filter(models.RainfallData.zone_id == zone_id)
            .order_by(models.RainfallData.date.desc())
            .first()
        )
        if latest_rainfall:
            rainfall_mm = latest_rainfall.rainfall_mm

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
        zone_id=zone_id,
        risk_score=score,
        risk_level=level,
        model_version="mock-v0",
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

    # Auto-fire an alert if risk is High.
    if level == models.RiskLevel.HIGH:
        dispatch_alert(
            db=db,
            zone_id=zone_id,
            message=f"HIGH landslide risk detected in zone '{zone.name}' (score={score}).",
            risk_prediction_id=prediction.id,
            alert_type="simulated",
        )

    return prediction


@router.get("/{zone_id}/risk/latest", response_model=schemas.RiskPredictionOut)
def latest_risk(zone_id: int, db: Session = Depends(get_db)):
    prediction = (
        db.query(models.RiskPrediction)
        .filter(models.RiskPrediction.zone_id == zone_id)
        .order_by(models.RiskPrediction.timestamp.desc())
        .first()
    )
    if not prediction:
        raise HTTPException(status_code=404, detail="No predictions yet for this zone")
    return prediction


@router.get("/{zone_id}/risk/history", response_model=List[schemas.RiskPredictionOut])
def risk_history(zone_id: int, hours: int = 24, db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return (
        db.query(models.RiskPrediction)
        .filter(
            models.RiskPrediction.zone_id == zone_id,
            models.RiskPrediction.timestamp >= cutoff,
        )
        .order_by(models.RiskPrediction.timestamp.asc())
        .all()
    )

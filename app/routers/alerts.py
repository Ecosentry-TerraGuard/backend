"""
routers/alerts.py — manually trigger an alert and view the alert log.

Automatic alerts (fired when a prediction comes back High) happen in
routers/risk.py. This file is for (a) the demo teammate to manually
fire an alert on cue during the presentation, and (b) the frontend to
display a log/history of alerts.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.alerts import dispatch_alert

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.post("/trigger", response_model=schemas.AlertLogOut, status_code=201)
def trigger_alert(payload: schemas.AlertTriggerRequest, db: Session = Depends(get_db)):
    """Manually fire an alert for a zone — handy for the live demo, so you
    don't have to wait for real sensor data to cross a threshold on stage."""
    zone = db.query(models.Zone).filter(models.Zone.id == payload.zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    message = payload.message or f"Manually triggered alert for zone '{zone.name}'."
    alert = dispatch_alert(
        db=db,
        zone_id=payload.zone_id,
        message=message,
        recipient=payload.recipient,
        alert_type="simulated",
    )
    return alert


@router.get("", response_model=List[schemas.AlertLogOut])
def list_alerts(zone_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Alert history — frontend's 'notifications' / activity feed panel."""
    query = db.query(models.AlertLog)
    if zone_id is not None:
        query = query.filter(models.AlertLog.zone_id == zone_id)
    return query.order_by(models.AlertLog.triggered_at.desc()).all()

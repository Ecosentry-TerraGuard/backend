"""
routers/sensors.py — endpoints for sensor nodes and their readings.

This is the file your IoT/ESP32 teammate cares about most: the
POST /readings endpoint is exactly what their firmware calls.
It's the frontend's main read path too (latest + history per zone).
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/v1", tags=["sensors"])


# ---------- Sensor node management ----------

@router.post("/nodes", response_model=schemas.SensorNodeOut, status_code=201)
def register_node(node: schemas.SensorNodeCreate, db: Session = Depends(get_db)):
    """Register a new physical ESP32 node against a zone. Usually done
    once per device, e.g. during setup/deployment."""
    zone = db.query(models.Zone).filter(models.Zone.id == node.zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")

    existing = db.query(models.SensorNode).filter(
        models.SensorNode.node_identifier == node.node_identifier
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Node identifier already registered")

    db_node = models.SensorNode(**node.model_dump())
    db.add(db_node)
    db.commit()
    db.refresh(db_node)
    return db_node


@router.get("/nodes", response_model=List[schemas.SensorNodeOut])
def list_nodes(zone_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.SensorNode)
    if zone_id is not None:
        query = query.filter(models.SensorNode.zone_id == zone_id)
    return query.all()


# ---------- Sensor readings (the ESP32 -> backend endpoint) ----------

@router.post("/readings", response_model=schemas.SensorReadingOut, status_code=201)
def push_reading(reading: schemas.SensorReadingCreate, db: Session = Depends(get_db)):
    """
    THE ESP32 ENDPOINT. Firmware POSTs here at regular intervals with its
    node_identifier and whatever sensor values it has (any can be null/omitted
    if that particular sensor isn't attached to a given node).

    We look up the node by its string identifier (not DB id) since that's
    what the firmware knows about itself.
    """
    node = db.query(models.SensorNode).filter(
        models.SensorNode.node_identifier == reading.node_identifier
    ).first()
    if not node:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown node_identifier '{reading.node_identifier}'. Register the node first via POST /api/v1/nodes.",
        )

    db_reading = models.SensorReading(
        node_id=node.id,
        timestamp=reading.timestamp or datetime.now(timezone.utc),
        soil_moisture=reading.soil_moisture,
        tilt_angle=reading.tilt_angle,
        vibration=reading.vibration,
        battery_voltage=reading.battery_voltage,
    )
    db.add(db_reading)

    # Track that this node is alive/reporting.
    node.last_seen_at = db_reading.timestamp

    db.commit()
    db.refresh(db_reading)
    return db_reading


@router.get("/zones/{zone_id}/readings/latest", response_model=List[schemas.SensorReadingOut])
def latest_readings_for_zone(zone_id: int, db: Session = Depends(get_db)):
    """Latest reading from EACH node in a zone — what the frontend dashboard
    shows for 'current conditions' on the zone's card/map marker."""
    node_ids = [n.id for n in db.query(models.SensorNode).filter(
        models.SensorNode.zone_id == zone_id
    ).all()]
    if not node_ids:
        return []

    results = []
    for node_id in node_ids:
        latest = (
            db.query(models.SensorReading)
            .filter(models.SensorReading.node_id == node_id)
            .order_by(models.SensorReading.timestamp.desc())
            .first()
        )
        if latest:
            results.append(latest)
    return results


@router.get("/zones/{zone_id}/readings/history", response_model=List[schemas.SensorReadingOut])
def reading_history_for_zone(
    zone_id: int,
    hours: int = 24,
    db: Session = Depends(get_db),
):
    """Historical readings across all nodes in a zone, for the frontend's
    trend charts. `hours` controls the lookback window (default 24h)."""
    node_ids = [n.id for n in db.query(models.SensorNode).filter(
        models.SensorNode.zone_id == zone_id
    ).all()]
    if not node_ids:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return (
        db.query(models.SensorReading)
        .filter(
            models.SensorReading.node_id.in_(node_ids),
            models.SensorReading.timestamp >= cutoff,
        )
        .order_by(models.SensorReading.timestamp.asc())
        .all()
    )

"""
routers/zones.py — endpoints for creating and listing zones.

WHAT'S AN APIRouter (FastAPI concept)?
Instead of putting every endpoint in one giant main.py, FastAPI lets
you group related endpoints into an APIRouter (like a mini-app), then
"include" it into the main app. Keeps each file focused on one resource.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/api/v1/zones", tags=["zones"])


@router.post("", response_model=schemas.ZoneOut, status_code=201)
def create_zone(zone: schemas.ZoneCreate, db: Session = Depends(get_db)):
    """Create a new monitored zone."""
    existing = db.query(models.Zone).filter(models.Zone.name == zone.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Zone with this name already exists")

    db_zone = models.Zone(**zone.model_dump())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    return db_zone


@router.get("", response_model=List[schemas.ZoneOut])
def list_zones(db: Session = Depends(get_db)):
    """List all zones — frontend uses this to populate the zone selector/map."""
    return db.query(models.Zone).all()


@router.get("/{zone_id}", response_model=schemas.ZoneOut)
def get_zone(zone_id: int, db: Session = Depends(get_db)):
    zone = db.query(models.Zone).filter(models.Zone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone

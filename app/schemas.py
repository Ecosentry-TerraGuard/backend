"""
schemas.py — Pydantic models = the shape of your API's requests/responses.

WHY THIS IS SEPARATE FROM models.py (FastAPI concept):
models.py defines your DATABASE tables (SQLAlchemy).
schemas.py defines your API's INPUT/OUTPUT shapes (Pydantic).
They usually look similar but serve different jobs: Pydantic validates
incoming JSON (rejects a request if a field is missing/wrong type) and
serializes outgoing data. Keeping them separate means you can, e.g.,
accept a request without an `id` field (the DB assigns it) but return
one in the response — and it means your DB schema can evolve without
automatically changing what the API exposes.

Naming convention used here:
    <Thing>Create  -> shape of data coming IN to create a record
    <Thing>Out     -> shape of data going OUT in a response
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models import RiskLevel, NodeStatus, AlertStatus


# ---------- Zones ----------

class ZoneCreate(BaseModel):
    name: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ZoneOut(BaseModel):
    # model_config lets Pydantic read attributes off a SQLAlchemy object
    # directly (model.name, model.id, ...) instead of requiring a dict.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime


# ---------- Sensor Nodes ----------

class SensorNodeCreate(BaseModel):
    node_identifier: str
    name: Optional[str] = None
    zone_id: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SensorNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_identifier: str
    name: Optional[str] = None
    zone_id: int
    status: NodeStatus
    last_seen_at: Optional[datetime] = None


# ---------- Sensor Readings ----------

class SensorReadingCreate(BaseModel):
    """
    This is what the ESP32 firmware POSTs. Kept minimal on purpose —
    the ESP32 identifies itself by `node_identifier` (a string it has
    hardcoded/knows), not by our internal DB id, since the firmware
    team shouldn't need to know our auto-generated ids.
    """
    node_identifier: str
    soil_moisture: Optional[float] = None
    tilt_angle: Optional[float] = None
    vibration: Optional[float] = None
    battery_voltage: Optional[float] = None
    # Optional: ESP32 can send its own timestamp; if omitted, server time is used.
    timestamp: Optional[datetime] = None


class SensorReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    timestamp: datetime
    soil_moisture: Optional[float] = None
    tilt_angle: Optional[float] = None
    vibration: Optional[float] = None
    battery_voltage: Optional[float] = None


# ---------- Risk Predictions ----------

class RiskPredictionOut(BaseModel):
    # protected_namespaces=() silences a harmless Pydantic warning: it
    # reserves the "model_" prefix by default (for its own internal use),
    # but our DB column is genuinely named model_version, so we opt out.
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    zone_id: int
    timestamp: datetime
    risk_score: float
    risk_level: RiskLevel
    model_version: str
    input_features: Optional[dict] = None


class RiskPredictTrigger(BaseModel):
    """
    Body for manually triggering a prediction (mostly for testing before
    sensors/ML are wired up). All fields optional — if omitted, the
    endpoint pulls the zone's latest stored readings/rainfall instead.
    """
    soil_moisture: Optional[float] = None
    tilt_angle: Optional[float] = None
    vibration: Optional[float] = None
    rainfall_mm: Optional[float] = None


# ---------- Alerts ----------

class AlertLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zone_id: int
    risk_prediction_id: Optional[int] = None
    triggered_at: datetime
    alert_type: str
    recipient: Optional[str] = None
    message: str
    status: AlertStatus


class AlertTriggerRequest(BaseModel):
    """Manually fire an alert for a zone (mostly for demo purposes)."""
    zone_id: int
    message: Optional[str] = None
    recipient: Optional[str] = None

"""
models.py — SQLAlchemy ORM models = your database tables.

Each class below becomes one SQL table. SQLAlchemy generates the
CREATE TABLE statements from these class definitions (see main.py,
Base.metadata.create_all). You never hand-write SQL DDL.

TABLES:
    zones            - a monitored geographic area (e.g. a hillside village)
    sensor_nodes     - a physical ESP32 unit installed in a zone
    sensor_readings  - one timestamped reading from a node
    rainfall_data    - daily rainfall figure for a zone (from public dataset)
    risk_predictions - one ML risk-score result for a zone at a point in time
    alert_logs       - a record of every alert that fired
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Enum, JSON, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    """Every timestamp in this system is stored in UTC to avoid timezone bugs
    when the ESP32 nodes, backend server, and frontend are all in IST."""
    return datetime.now(timezone.utc)


class RiskLevel(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class NodeStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAULTY = "faulty"


class AlertStatus(str, enum.Enum):
    SIMULATED = "simulated"
    SENT = "sent"
    FAILED = "failed"


class Zone(Base):
    """A geographic area being monitored — e.g. one village/hillside sector.
    Everything else (sensors, rainfall, risk, alerts) hangs off a zone."""
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    sensor_nodes = relationship("SensorNode", back_populates="zone")
    rainfall_records = relationship("RainfallData", back_populates="zone")
    risk_predictions = relationship("RiskPrediction", back_populates="zone")
    alert_logs = relationship("AlertLog", back_populates="zone")


class SensorNode(Base):
    """A physical ESP32 device installed in a zone. `node_identifier` is
    the unique ID the ESP32 firmware sends (e.g. its MAC address or a
    hardcoded string like 'ESP32-NODE-04') — this is how we recognize
    which physical device a reading came from."""
    __tablename__ = "sensor_nodes"

    id = Column(Integer, primary_key=True, index=True)
    node_identifier = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, nullable=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    status = Column(Enum(NodeStatus), default=NodeStatus.ACTIVE)
    installed_at = Column(DateTime(timezone=True), default=utcnow)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    zone = relationship("Zone", back_populates="sensor_nodes")
    readings = relationship("SensorReading", back_populates="node")


class SensorReading(Base):
    """One timestamped reading pushed by an ESP32 node. Kept flat/simple —
    every reading is one row, indexed by node + time so 'give me the last
    24h for this node/zone' queries stay fast."""
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("sensor_nodes.id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True)

    soil_moisture = Column(Float, nullable=True)   # % volumetric water content
    tilt_angle = Column(Float, nullable=True)       # degrees from vertical
    vibration = Column(Float, nullable=True)        # arbitrary sensor unit / g-force
    battery_voltage = Column(Float, nullable=True)  # optional node health signal

    node = relationship("SensorNode", back_populates="readings")


class RainfallData(Base):
    """Daily rainfall figure for a zone, backfilled from a public dataset
    since no official NER (North Eastern Region) dataset exists yet."""
    __tablename__ = "rainfall_data"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    rainfall_mm = Column(Float, nullable=False)
    source = Column(String, default="public_dataset")

    zone = relationship("Zone", back_populates="rainfall_records")


class RiskPrediction(Base):
    """One ML risk-assessment result for a zone at a point in time. We keep
    every prediction (not just the latest) so the frontend can plot a risk
    trend line, and so you have a demo-able 'history' to show judges."""
    __tablename__ = "risk_predictions"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True)

    risk_score = Column(Float, nullable=False)          # raw 0.0–1.0 from the model
    risk_level = Column(Enum(RiskLevel), nullable=False)  # bucketed Low/Medium/High
    model_version = Column(String, default="mock-v0")
    # input_features stores exactly what was fed to the model (soil moisture,
    # tilt, vibration, rainfall at prediction time) as JSON — useful for
    # debugging and for your ML teammates to sanity-check what they received.
    input_features = Column(JSON, nullable=True)

    zone = relationship("Zone", back_populates="risk_predictions")


class AlertLog(Base):
    """Record of every alert fired, real or simulated. Keeping alerts even
    when simulated means you have a demo-able audit trail without needing
    working SMS/email integration."""
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=False, index=True)
    risk_prediction_id = Column(Integer, ForeignKey("risk_predictions.id"), nullable=True)
    triggered_at = Column(DateTime(timezone=True), default=utcnow)
    alert_type = Column(String, default="simulated")  # "sms" | "email" | "simulated"
    recipient = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    status = Column(Enum(AlertStatus), default=AlertStatus.SIMULATED)

    zone = relationship("Zone", back_populates="alert_logs")

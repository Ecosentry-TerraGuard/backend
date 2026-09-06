"""
ml_client.py — the ONE function your ML teammates need to replace.

WHY THIS FILE EXISTS:
Your backend needs to "call the ML model" but the model isn't ready yet.
Rather than blocking on that, this file isolates the ML call behind a
single function with a fixed input/output shape. Right now it's a mock
(simple threshold rule + a bit of randomness). When the ML team has
their Random Forest / Logistic Regression model ready, they (or you)
swap out the BODY of predict_risk() to load their pickled model and
call .predict() — nothing else in the codebase has to change, because
the function signature stays the same.

HAND THIS FILE + THE FUNCTION SIGNATURE TO YOUR ML TEAMMATES.
"""

import random
from app.models import RiskLevel


def score_to_level(score: float) -> RiskLevel:
    """Buckets a raw 0.0-1.0 risk score into Low/Medium/High.
    Thresholds are placeholders — tune with your ML team once real
    model outputs are available."""
    if score >= 0.7:
        return RiskLevel.HIGH
    elif score >= 0.4:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW


def predict_risk(
    soil_moisture: float,
    rainfall_mm: float,
    slope: float,
    ndvi: float,
    landslide_density: float,
) -> tuple[float, RiskLevel]:
    """
    Returns (risk_score, risk_level) using live sensor + rainfall data
    combined with static per-zone geospatial features. Tilt is
    deliberately NOT a model input — see check_tilt_escalation() below.
    """
    # Simple weighted mock: higher soil moisture and rainfall push the score up.
    # Static features (slope, ndvi, landslide_density) are also factored in.
    # This is NOT a real model — it exists so the rest of the system (DB, API,
    # alerts, frontend) can be built and demoed before the real model is plugged in.
    soil_moisture = max(0.0, soil_moisture)
    rainfall_mm = max(0.0, rainfall_mm)
    slope = max(0.0, slope)  # Ensure non-negative
    ndvi = max(-1.0, min(1.0, ndvi))  # Clamp NDVI to valid range
    landslide_density = max(0.0, landslide_density)  # Ensure non-negative

    # Normalize inputs to 0-1 range for consistent weighting
    # Soil moisture: typical range 0-100%
    # Rainfall: typical daily range 0-100mm
    # Slope: typical range 0-90 degrees
    # NDVI: already -1 to 1, shift to 0-1
    # Landslide density: assume typical range 0-1 for demo
    norm_soil_moisture = min(soil_moisture / 100, 1.0)
    norm_rainfall = min(rainfall_mm / 100, 1.0)
    norm_slope = min(slope / 90, 1.0)
    norm_ndvi = (ndvi + 1) / 2  # Shift from -1,1 to 0,1
    norm_landslide = min(landslide_density, 1.0)  # Assume max 1.0 for demo

    # Weighted combination - live features (soil moisture, rainfall) get higher weight
    # in this mock since they're more dynamic; static features provide baseline risk
    normalized = (
        norm_soil_moisture * 0.30
        + norm_rainfall * 0.30
        + norm_slope * 0.15
        + norm_ndvi * 0.15
        + norm_landslide * 0.10
    )
    # small jitter so repeated calls with identical inputs aren't
    # perfectly identical — makes the demo look "alive"
    noise = random.uniform(-0.05, 0.05)
    score = max(0.0, min(1.0, normalized + noise))

    return round(score, 3), score_to_level(score)


def check_tilt_escalation(tilt_angle: float, tilt_baseline: float) -> bool:
    """
    Returns True if tilt has moved sharply enough above baseline to
    warrant escalating an already-elevated risk level, regardless of
    what the ML model predicted. Historical tilt data doesn't exist
    for training, so tilt is used as a live safety override instead
    of a trained feature.
    """
    # Simple escalation logic: if tilt exceeds baseline by more than 10 degrees
    # or by 50% of baseline (whichever is greater), trigger escalation
    if tilt_baseline <= 0:
        # Avoid division by zero or negative baseline
        return tilt_angle > 10.0

    absolute_increase = tilt_angle - tilt_baseline
    relative_increase = absolute_increase / tilt_baseline if tilt_baseline > 0 else float('inf')

    # Trigger if absolute increase > 10 degrees OR relative increase > 50%
    return absolute_increase > 10.0 or relative_increase > 0.5

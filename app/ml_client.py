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
    soil_moisture: float | None,
    tilt_angle: float | None,
    vibration: float | None,
    rainfall_mm: float | None,
) -> tuple[float, RiskLevel]:
    """
    MOCK IMPLEMENTATION — replace the body of this function with a real
    model call once it's ready. Keep the signature (inputs/outputs)
    the same so nothing else in the backend needs to change.

    Expected replacement, roughly:
        import joblib
        _model = joblib.load("model.pkl")

        def predict_risk(soil_moisture, tilt_angle, vibration, rainfall_mm):
            features = [[soil_moisture or 0, tilt_angle or 0,
                         vibration or 0, rainfall_mm or 0]]
            score = _model.predict_proba(features)[0][1]  # prob. of landslide class
            return score, score_to_level(score)

    Returns:
        (risk_score, risk_level) where risk_score is a float 0.0-1.0
    """
    # Simple weighted mock: higher soil moisture, tilt, vibration, and
    # rainfall push the score up. This is NOT a real model — it exists
    # so the rest of the system (DB, API, alerts, frontend) can be
    # built and demoed before the real model is plugged in.
    soil_moisture = soil_moisture or 0
    tilt_angle = tilt_angle or 0
    vibration = vibration or 0
    rainfall_mm = rainfall_mm or 0

    normalized = (
        min(soil_moisture / 100, 1.0) * 0.35
        + min(tilt_angle / 45, 1.0) * 0.30
        + min(vibration / 10, 1.0) * 0.20
        + min(rainfall_mm / 100, 1.0) * 0.15
    )
    # small jitter so repeated calls with identical inputs aren't
    # perfectly identical — makes the demo look "alive"
    noise = random.uniform(-0.05, 0.05)
    score = max(0.0, min(1.0, normalized + noise))

    return round(score, 3), score_to_level(score)

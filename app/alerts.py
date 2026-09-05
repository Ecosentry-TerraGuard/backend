"""
alerts.py — sending (or simulating) an alert.

Same pattern as ml_client.py: one function, `dispatch_alert`, isolates
the "actually send SMS/email" logic. Right now it just logs and marks
the alert as SIMULATED. If you get time to wire up Twilio or SMTP,
you only change the inside of this function.
"""

from sqlalchemy.orm import Session
from app.models import AlertLog, AlertStatus

# Flip this to True once Twilio/SMTP credentials are wired up.
REAL_ALERTS_ENABLED = False


def dispatch_alert(
    db: Session,
    zone_id: int,
    message: str,
    recipient: str | None = None,
    risk_prediction_id: int | None = None,
    alert_type: str = "simulated",
) -> AlertLog:
    """
    Creates an AlertLog row and (if REAL_ALERTS_ENABLED) actually sends it.

    Example Twilio swap-in, once you have credentials:
        from twilio.rest import Client
        client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        client.messages.create(body=message, from_=TWILIO_FROM, to=recipient)

    Example SMTP swap-in:
        import smtplib
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, recipient, message)
    """
    status = AlertStatus.SIMULATED

    if REAL_ALERTS_ENABLED:
        try:
            # real send logic would go here
            status = AlertStatus.SENT
        except Exception:
            status = AlertStatus.FAILED

    alert = AlertLog(
        zone_id=zone_id,
        risk_prediction_id=risk_prediction_id,
        alert_type=alert_type,
        recipient=recipient,
        message=message,
        status=status,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert

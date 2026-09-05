"""
main.py — the FastAPI application entrypoint.

Run it with:
    uvicorn app.main:app --reload --port 8000

Then open http://localhost:8000/docs for the auto-generated interactive
API docs (Swagger UI) — FastAPI builds this automatically from your
Pydantic schemas, no extra work needed. This is the single most useful
thing to hand your frontend/ML teammates: they can try every endpoint
in the browser before writing any of their own integration code.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import zones, sensors, risk, alerts, seed

# Creates all tables defined in models.py if they don't already exist.
# For a hackathon this replaces writing/running migrations — fine here,
# NOT how you'd do it in a real production system (you'd use Alembic).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TerraGuard API",
    description="Backend for TerraGuard — AI-powered landslide early warning system (SIH26001)",
    version="0.1.0",
)

# CORS: allows your frontend (running on a different port/origin, e.g.
# localhost:3000 for a React dev server) to call this API from the
# browser. Wide open ("*") is fine for a hackathon demo; you'd restrict
# this to your actual frontend's domain in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(zones.router)
app.include_router(sensors.router)
app.include_router(risk.router)
app.include_router(alerts.router)
app.include_router(seed.router)


@app.get("/", tags=["health"])
def health_check():
    """Simple liveness check — hit this to confirm the server is up."""
    return {"status": "ok", "service": "TerraGuard API", "version": "0.1.0"}

"""
database.py — sets up the SQLAlchemy engine and session.

WHY THIS FILE EXISTS (FastAPI/SQLAlchemy concept):
FastAPI itself doesn't know anything about databases. SQLAlchemy is the
library that talks to the actual DB (SQLite or Postgres) and gives us
Python objects instead of raw SQL. This file just wires that up once,
so every other file can import `get_db` and use it.

SWITCHING TO POSTGRES LATER:
Just set the DATABASE_URL environment variable, e.g.:
    export DATABASE_URL="postgresql://user:password@localhost:5432/terraguard"
If it's not set, we default to a local SQLite file — zero setup for
teammates who just want to run the API.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./terraguard.db")

# connect_args is only needed for SQLite (allows use across threads,
# which FastAPI's async workers need). Postgres doesn't need this arg.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class all our ORM models (tables) inherit from."""
    pass


def get_db():
    """
    FastAPI "dependency injection" pattern.

    WHAT THIS MEANS (FastAPI concept): instead of every route function
    manually opening and closing a DB connection, we declare this
    function as a dependency. FastAPI calls it before your route runs,
    hands your route the `db` session it `yield`s, and automatically
    runs the code after `yield` (closing the session) once your route
    finishes — even if it raised an error. You'll see this used as:

        def my_route(db: Session = Depends(get_db)):
            ...

    This keeps connection handling out of every single endpoint.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""SQLAlchemy engine/session wiring.

The whole app talks to a single local SQLite file. Keeping the connection
setup in one module means the API, the seed script, and the tests all share
the same configuration.
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# The DB lives next to the backend package so `git clone && seed` just works.
DB_PATH = Path(__file__).resolve().parent.parent / "cashflow.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# check_same_thread=False lets FastAPI's threadpool share the connection.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""


def get_db():
    """FastAPI dependency that yields a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""Database configuration for the CargoPulse API."""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from pipeline.config import load_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the shared SQLAlchemy database engine."""

    settings = load_settings()

    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )

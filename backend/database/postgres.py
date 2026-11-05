"""
PostgreSQL connection management using SQLAlchemy.
Allows direct integration with pgAdmin and cloud PostgreSQL instances.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)

# Credentials from .env
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "portfolio_mlops_db")

# Complete Database URL (falls back to individual env variables)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

# Standardize protocol if needed
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLAlchemy engine & session factory
engine = None
SessionLocal = None
Base = declarative_base()


def get_engine():
    global engine, SessionLocal
    if engine is None:
        try:
            engine = create_engine(
                DATABASE_URL,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        except Exception as exc:
            logger.error("Failed to create PostgreSQL engine: %s", exc)
            raise
    return engine


def get_session_factory():
    if SessionLocal is None:
        get_engine()
    return SessionLocal


def get_pg_db():
    """FastAPI dependency for injecting PostgreSQL session into route handlers."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """Context manager for standalone/service database sessions."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def test_postgres_connection() -> dict:
    """Verifies connection to PostgreSQL and returns database info."""
    eng = get_engine()
    with eng.connect() as conn:
        result = conn.execute(text("SELECT version();")).scalar()
        db_name = conn.execute(text("SELECT current_database();")).scalar()
        return {
            "status": "connected",
            "database": db_name,
            "version": result,
            "host": POSTGRES_HOST,
            "port": POSTGRES_PORT,
        }


def init_postgres() -> bool:
    """Creates all defined PostgreSQL tables in the database upon startup."""
    try:
        eng = get_engine()
        # Import models so Base has all table metadata registered
        from backend.database import pg_models  # noqa: F401

        Base.metadata.create_all(bind=eng)
        info = test_postgres_connection()
        logger.info(
            "PostgreSQL connected successfully → db=%s (host=%s:%s)",
            info["database"],
            POSTGRES_HOST,
            POSTGRES_PORT,
        )
        return True
    except Exception as exc:
        logger.warning(
            "PostgreSQL not connected or credentials not set: %s. Continuing with MongoDB.",
            exc,
        )
        return False

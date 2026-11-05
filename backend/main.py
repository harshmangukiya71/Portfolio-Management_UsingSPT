"""
FastAPI application entrypoint (PostgreSQL-backed).
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from backend.api import auth, model, portfolio
from backend.database.postgres import init_postgres, test_postgres_connection
from backend.services.ml_service import load_checkpoint_if_exists
from backend.services.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== AI Portfolio Manager starting up ===")

    # Initialize PostgreSQL (pgAdmin tables)
    init_postgres()

    # Load existing model checkpoint (if any)
    load_checkpoint_if_exists()

    # Start rebalancing scheduler
    start_scheduler()

    yield

    # Shutdown
    logger.info("=== Shutting down ===")
    shutdown_scheduler()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Portfolio Manager API",
    description="Production-grade AI portfolio management using Functional SPT + GARCH backed by PostgreSQL",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,https://portfolio-ai.vercel.app",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router,      prefix="/auth",      tags=["Authentication"])
app.include_router(portfolio.router, prefix="/portfolio",  tags=["Portfolio"])
app.include_router(model.router,     prefix="/model",      tags=["Model"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/db/postgres-status", tags=["Database"])
def postgres_status():
    """Check connectivity to PostgreSQL / pgAdmin database."""
    try:
        info = test_postgres_connection()
        return {"status": "connected", "details": info}
    except Exception as exc:
        return {
            "status": "disconnected",
            "message": str(exc),
            "hint": "Check that PostgreSQL service is running and DB credentials in .env are correct."
        }


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "AI Portfolio Manager API",
        "docs":    "/docs",
        "health":  "/health",
        "db":      "/db/postgres-status",
    }

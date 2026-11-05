"""
APScheduler — periodic rebalancing every 21 trading days (PostgreSQL-backed).

Runs as a background task inside the FastAPI process.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.database.pg_models import Portfolio, RebalanceHistory
from backend.database.postgres import get_db_session
from backend.services import ml_service

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler()
_REBALANCE_DAYS = int(os.getenv("REBALANCE_DAYS", "21"))


def start_scheduler() -> None:
    """Called on app startup — starts the background scheduler."""
    _scheduler.add_job(
        _rebalance_all_portfolios,
        trigger=IntervalTrigger(days=_REBALANCE_DAYS),
        id="periodic_rebalance",
        replace_existing=True,
        next_run_time=None,   # don't run immediately at startup
    )
    _scheduler.start()
    logger.info(
        "Scheduler started — rebalance every %d days", _REBALANCE_DAYS
    )


def shutdown_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


async def _rebalance_all_portfolios() -> None:
    """Retrain model and rebalance every active portfolio."""
    logger.info("=== Scheduled rebalance triggered ===")

    with get_db_session() as db:
        portfolios = (
            db.query(Portfolio)
            .filter(Portfolio.status == "active")
            .limit(500)
            .all()
        )
        portfolios_data = [
            {"id": p.id, "stocks": list(p.stocks or [])}
            for p in portfolios
        ]

    if not portfolios_data:
        logger.info("No active portfolios to rebalance")
        return

    for p_item in portfolios_data:
        portfolio_id = p_item["id"]
        stocks = p_item["stocks"]

        if not stocks:
            continue

        try:
            logger.info("Rebalancing portfolio %d (%d stocks)", portfolio_id, len(stocks))

            # Retrain model for this stock set
            await ml_service.retrain(stocks)

            now = datetime.now(timezone.utc)
            with get_db_session() as db:
                p = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
                if p:
                    p.last_rebalanced = now

                    reb = RebalanceHistory(
                        portfolio_id=portfolio_id,
                        date=now,
                        old_weights={},
                        new_weights={},
                        turnover=0.0,
                        transaction_cost=0.0,
                    )
                    db.add(reb)
                    db.commit()

            logger.info("Portfolio %d rebalanced successfully", portfolio_id)

        except Exception as exc:
            logger.exception(
                "Failed to rebalance portfolio %d: %s", portfolio_id, exc
            )

    logger.info("=== Scheduled rebalance complete (%d portfolios) ===", len(portfolios_data))

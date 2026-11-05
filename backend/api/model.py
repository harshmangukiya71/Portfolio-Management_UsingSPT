"""
Model API — retrain, status, metrics endpoints using PostgreSQL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc

from backend.api.auth import get_current_user
from backend.database.models import UserOut
from backend.database.pg_models import ModelMetrics, Portfolio
from backend.database.postgres import get_db_session
from backend.services import ml_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/retrain")
async def retrain_model(
    portfolio_id: str,
    user: UserOut = Depends(get_current_user),
):
    """
    POST /model/retrain?portfolio_id=...

    Manually trigger model retraining for a portfolio's stock set.
    """
    p_id = int(portfolio_id)
    u_id = int(user.id) if user.id and str(user.id).isdigit() else None

    with get_db_session() as db:
        query = db.query(Portfolio).filter(Portfolio.id == p_id)
        if u_id is not None:
            query = query.filter(Portfolio.user_id == u_id)
        p = query.first()
        if not p:
            raise HTTPException(status_code=404, detail="Portfolio not found")
        stocks = list(p.stocks or [])

    try:
        metrics = await ml_service.train_now(stocks)
    except Exception as exc:
        with get_db_session() as db:
            p = db.query(Portfolio).filter(Portfolio.id == p_id).first()
            if p:
                p.status = "error"
                p.model_trained = False
                db.commit()
        raise HTTPException(status_code=500, detail=str(exc))

    now = datetime.now(timezone.utc)
    with get_db_session() as db:
        p = db.query(Portfolio).filter(Portfolio.id == p_id).first()
        if p:
            p.status = "active"
            p.model_trained = True
            p.last_rebalanced = now

            if isinstance(metrics, dict):
                mm = ModelMetrics(
                    portfolio_id=p.id,
                    date=now,
                    sharpe_gross=float(metrics.get("sharpe_gross", metrics.get("sharpe", 0.0))),
                    sharpe_net=float(metrics.get("sharpe_net", 0.0)),
                    annual_return=float(metrics.get("annual_return", metrics.get("arithmetic_return", 0.0))),
                    volatility=float(metrics.get("volatility", 0.0)),
                    max_drawdown=float(metrics.get("max_drawdown", 0.0)),
                    training_duration_s=float(metrics.get("training_duration_s", 0.0)),
                    epochs=int(metrics.get("epochs", 50)),
                )
                db.add(mm)
            db.commit()

    return {
        "message": "Model training complete",
        "stocks": stocks,
        "status": "done",
        "metrics": metrics,
    }


@router.get("/status")
async def model_status(user: UserOut = Depends(get_current_user)):
    """Return current ML model training status."""
    return await ml_service.get_status()


@router.get("/metrics")
async def model_metrics(
    portfolio_id: str,
    limit: int = 10,
    user: UserOut = Depends(get_current_user),
):
    """Return the last N model metric records for a portfolio from PostgreSQL."""
    p_id = int(portfolio_id)
    with get_db_session() as db:
        records = (
            db.query(ModelMetrics)
            .filter(ModelMetrics.portfolio_id == p_id)
            .order_by(desc(ModelMetrics.date))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": str(r.id),
                "portfolio_id": str(r.portfolio_id),
                "date": r.date,
                "sharpe_gross": r.sharpe_gross,
                "sharpe_net": r.sharpe_net,
                "annual_return": r.annual_return,
                "volatility": r.volatility,
                "max_drawdown": r.max_drawdown,
                "training_duration_s": r.training_duration_s,
                "epochs": r.epochs,
            }
            for r in records
        ]

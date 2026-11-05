"""
Portfolio API — all portfolio management endpoints.
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.auth import get_current_user
from backend.database.models import (
    AddStockRequest,
    AddStocksRequest,
    ExitStockRequest,
    PortfolioCreate,
    PortfolioOut,
    RemoveStockRequest,
    ReinvestFromPocketRequest,
    UserOut,
)
from backend.services import portfolio_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Portfolio CRUD
# ---------------------------------------------------------------------------

@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    payload: PortfolioCreate,
    user: UserOut = Depends(get_current_user),
):
    """
    Create a new AI-managed portfolio.

    - Persists portfolio to MongoDB
    - Triggers background model training
    - Returns portfolio document immediately (status = 'training')
    """
    try:
        portfolio = await portfolio_service.create_portfolio(user.id, payload)
        return portfolio
    except Exception as exc:
        logger.exception("create_portfolio failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/list", response_model=List[dict])
async def list_portfolios(user: UserOut = Depends(get_current_user)):
    """Return all portfolios for the current user."""
    return await portfolio_service.list_portfolios(user.id)


# ---------------------------------------------------------------------------
# Stock management
# ---------------------------------------------------------------------------

@router.post("/add-stock")
async def add_stock(
    payload: AddStockRequest,
    user: UserOut = Depends(get_current_user),
):
    """
    Add a stock to the portfolio.

    - Validates ticker is not already present
    - Triggers model retrain with expanded universe
    - Returns updated stock list
    """
    try:
        return await portfolio_service.add_stock(
            payload.portfolio_id, user.id, payload.ticker
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("add_stock failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/add-stocks")
async def add_stocks(
    payload: AddStocksRequest,
    user: UserOut = Depends(get_current_user),
):
    """Add several stocks to a portfolio and trigger one retrain."""
    try:
        return await portfolio_service.add_stocks(
            payload.portfolio_id, user.id, payload.tickers
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("add_stocks failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/remove-stock")
async def remove_stock(
    payload: RemoveStockRequest,
    user: UserOut = Depends(get_current_user),
):
    """
    Remove a stock from the portfolio.

    - Capital is NOT left idle — redistributed proportionally
      to remaining stocks via the next model inference
    - Triggers model retrain with reduced universe
    """
    try:
        return await portfolio_service.remove_stock(
            payload.portfolio_id, user.id, payload.ticker
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("remove_stock failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/exit-stock")
async def exit_stock(
    payload: ExitStockRequest,
    user: UserOut = Depends(get_current_user),
):
    """
    Exit a stock, move requested amount to cash pocket, and reinvest the rest
    across remaining stocks through normalized model weights.
    """
    try:
        return await portfolio_service.exit_stock(
            payload.portfolio_id,
            user.id,
            payload.ticker,
            payload.withdraw_amount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("exit_stock failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
@router.post("/reinvest-from-pocket")
async def reinvest_from_pocket(
    payload: ReinvestFromPocketRequest,
    user: UserOut = Depends(get_current_user),
):
    """
    Reinvest a specified amount from pocket (cash balance) into remaining holdings
    proportionally using normalized weights without retraining.
    """
    try:
        return await portfolio_service.reinvest_from_pocket(
            payload.portfolio_id,
            user.id,
            payload.amount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("reinvest_from_pocket failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# Weights & Performance
# ---------------------------------------------------------------------------

@router.get("/weights")
async def get_weights(
    portfolio_id: str,
    user: UserOut = Depends(get_current_user),
):
    """
    GET /portfolio/weights?portfolio_id=...

    Returns current model weights + ₹ allocations.
    If model not trained → returns equal weights with model_trained=false.
    """
    try:
        return await portfolio_service.get_weights(portfolio_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("get_weights failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/performance")
async def get_performance(
    portfolio_id: str,
    user: UserOut = Depends(get_current_user),
):
    """
    GET /portfolio/performance?portfolio_id=...

    Returns full backtest metrics + time series for charts:
    - Sharpe, return, volatility, max drawdown
    - Cumulative wealth (gross, net, market)
    - Relative wealth
    - Turnover
    - Weights history
    """
    try:
        return await portfolio_service.get_performance(portfolio_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("get_performance failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Rebalance
# ---------------------------------------------------------------------------

@router.post("/rebalance")
async def rebalance(
    portfolio_id: str,
    user: UserOut = Depends(get_current_user),
):
    """
    POST /portfolio/rebalance?portfolio_id=...

    Force a rebalance cycle:
    1. Retrain model
    2. Compute new weights
    3. Calculate turnover + transaction costs
    4. Persist rebalance record
    """
    try:
        return await portfolio_service.rebalance(portfolio_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("rebalance failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Capital update
# ---------------------------------------------------------------------------

@router.patch("/{portfolio_id}/capital")
async def update_capital(
    portfolio_id: str,
    capital: float,
    user: UserOut = Depends(get_current_user),
):
    """Update total portfolio capital."""
    if capital <= 0:
        raise HTTPException(status_code=400, detail="Capital must be positive")
    try:
        return await portfolio_service.update_capital(portfolio_id, user.id, capital)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{portfolio_id}")
async def get_portfolio(
    portfolio_id: str,
    user: UserOut = Depends(get_current_user),
):
    """Return a single portfolio by ID."""
    doc = await portfolio_service.get_portfolio(portfolio_id, user.id)
    if not doc:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return doc

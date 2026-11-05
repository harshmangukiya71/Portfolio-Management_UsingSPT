"""
Portfolio business logic service — backed completely by PostgreSQL / SQLAlchemy.

All database writes live here so API routes stay thin.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc

from backend.database.models import PortfolioCreate
from backend.database.pg_models import (
    Portfolio,
    RebalanceHistory,
    Transaction,
    WeightHistory,
)
from backend.database.postgres import get_db_session
from backend.services import ml_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(p: Optional[Portfolio]) -> Optional[Dict]:
    """Convert PostgreSQL Portfolio ORM instance to JSON-serializable dict."""
    if not p:
        return None
    return {
        "id": str(p.id),
        "user_id": str(p.user_id) if p.user_id is not None else None,
        "name": p.name,
        "stocks": p.stocks or [],
        "capital": float(p.capital),
        "cash_balance": float(p.cash_balance or 0.0),
        "status": p.status,
        "model_trained": bool(p.model_trained),
        "created_at": p.created_at,
        "last_rebalanced": p.last_rebalanced,
    }


def _get_portfolio_or_raise(db, portfolio_id: int | str, user_id: int | str) -> Portfolio:
    p_id = int(portfolio_id)
    u_id = int(user_id) if user_id is not None else None
    query = db.query(Portfolio).filter(Portfolio.id == p_id)
    if u_id is not None:
        query = query.filter(Portfolio.user_id == u_id)
    p = query.first()
    if not p:
        raise ValueError(f"Portfolio {portfolio_id} not found")
    return p


def _log_transaction(db, portfolio_id: int | str, tx_type: str, details: Dict) -> None:
    tx = Transaction(
        portfolio_id=int(portfolio_id),
        date=datetime.now(timezone.utc),
        type=tx_type,
        details=details,
    )
    db.add(tx)


# ---------------------------------------------------------------------------
# Portfolio CRUD
# ---------------------------------------------------------------------------

async def create_portfolio(user_id: str, payload: PortfolioCreate) -> Dict:
    """Create portfolio record in PostgreSQL and trigger initial model training."""
    u_id = int(user_id) if user_id and str(user_id).isdigit() else None
    stocks_cleaned = [t.upper().strip() for t in payload.stocks]

    with get_db_session() as db:
        p = Portfolio(
            user_id=u_id,
            name=payload.name,
            stocks=stocks_cleaned,
            capital=float(payload.capital),
            cash_balance=0.0,
            status="training",
            model_trained=False,
            created_at=datetime.now(timezone.utc),
            last_rebalanced=None,
        )
        db.add(p)
        db.flush()  # Populates p.id

        _log_transaction(
            db,
            p.id,
            "create",
            {"stocks": stocks_cleaned, "capital": payload.capital},
        )
        db.commit()
        db.refresh(p)
        result_dict = _fmt(p)

    # Trigger initial training in background
    await ml_service.retrain(stocks_cleaned)
    return result_dict


async def get_portfolio(portfolio_id: str, user_id: str) -> Optional[Dict]:
    with get_db_session() as db:
        try:
            p = _get_portfolio_or_raise(db, portfolio_id, user_id)
            return _fmt(p)
        except ValueError:
            return None


async def list_portfolios(user_id: str) -> List[Dict]:
    u_id = int(user_id) if user_id and str(user_id).isdigit() else None
    with get_db_session() as db:
        query = db.query(Portfolio)
        if u_id is not None:
            query = query.filter(Portfolio.user_id == u_id)
        portfolios = query.all()
        return [_fmt(p) for p in portfolios]


# ---------------------------------------------------------------------------
# Stock management
# ---------------------------------------------------------------------------

async def add_stock(portfolio_id: str, user_id: str, ticker: str) -> Dict:
    """Add a stock to the portfolio and trigger rebalancing."""
    ticker = ticker.upper().strip()

    with get_db_session() as db:
        p = _get_portfolio_or_raise(db, portfolio_id, user_id)
        current_stocks = list(p.stocks or [])
        if ticker in current_stocks:
            raise ValueError(f"{ticker} is already in the portfolio")

        new_stocks = current_stocks + [ticker]
        p.stocks = new_stocks
        p.status = "training"
        p.model_trained = False

        _log_transaction(db, p.id, "add_stock", {"ticker": ticker})
        db.commit()

    # Retrain with new stock set
    await ml_service.retrain(new_stocks)
    return {"message": f"{ticker} added. Model retraining started.", "stocks": new_stocks}


async def add_stocks(portfolio_id: str, user_id: str, tickers: List[str]) -> Dict:
    """Add multiple stocks and trigger a single retrain for the final universe."""
    cleaned = []
    for ticker in tickers:
        t = ticker.upper().strip()
        if t and t not in cleaned:
            cleaned.append(t)

    if not cleaned:
        raise ValueError("Select at least one stock")

    with get_db_session() as db:
        p = _get_portfolio_or_raise(db, portfolio_id, user_id)
        existing = set(p.stocks or [])
        to_add = [ticker for ticker in cleaned if ticker not in existing]
        if not to_add:
            raise ValueError("Selected stocks are already in the portfolio")

        new_stocks = list(p.stocks or []) + to_add
        p.stocks = new_stocks
        p.status = "training"
        p.model_trained = False

        _log_transaction(db, p.id, "add_stocks", {"tickers": to_add})
        db.commit()

    await ml_service.retrain(new_stocks)
    return {
        "message": f"{len(to_add)} stocks added. Model retraining started.",
        "added": to_add,
        "stocks": new_stocks,
    }


async def remove_stock(portfolio_id: str, user_id: str, ticker: str) -> Dict:
    """Remove a stock and proportionally redistribute its capital without retraining."""
    return await exit_stock(portfolio_id, user_id, ticker, withdraw_amount=0.0)


async def exit_stock(
    portfolio_id: str,
    user_id: str,
    ticker: str,
    withdraw_amount: float,
) -> Dict:
    """
    Exit a stock, optionally move part of its current allocation to cash pocket,
    and reinvest the remainder proportionally across remaining stocks by normalizing
    their weights without retraining.
    """
    ticker = ticker.upper().strip()

    with get_db_session() as db:
        p = _get_portfolio_or_raise(db, portfolio_id, user_id)
        stocks = list(p.stocks or [])
        if ticker not in stocks:
            raise ValueError(f"{ticker} is not in the portfolio")

        remaining = [t for t in stocks if t != ticker]
        capital = float(p.capital)

        # 1. Fetch current weights and allocations before exit
        latest_wh = (
            db.query(WeightHistory)
            .filter(WeightHistory.portfolio_id == p.id)
            .order_by(desc(WeightHistory.date))
            .first()
        )
        if latest_wh and latest_wh.weights and ticker in latest_wh.weights:
            weight_map = {t: float(latest_wh.weights.get(t, 0.0)) for t in stocks}
            allocation_map = {
                t: float(latest_wh.allocations.get(t, weight_map.get(t, 0.0) * capital))
                for t in stocks
            }
            exited_value = float(allocation_map.get(ticker, capital / len(stocks)))
        else:
            allocations, _ = await ml_service.get_weights(stocks, capital)
            weight_map = {a["ticker"]: float(a["weight"]) for a in allocations}
            allocation_map = {a["ticker"]: float(a["allocation_inr"]) for a in allocations}
            exited_value = float(allocation_map.get(ticker, capital / len(stocks)))

        # 2. Last stock: liquidate everything to pocket
        if not remaining:
            full_pocket = float(p.cash_balance or 0.0) + exited_value
            p.stocks = []
            p.capital = 0.0
            p.cash_balance = full_pocket
            p.status = "idle"
            p.model_trained = False

            _log_transaction(db, p.id, "exit_stock", {
                "ticker": ticker,
                "exited_value": exited_value,
                "withdrawn_to_pocket": exited_value,
                "reinvested": 0.0,
                "remaining": [],
                "note": "Last stock — full value moved to pocket",
            })
            db.commit()
            return {
                "message": f"Exited last holding {ticker}. Full value moved to pocket.",
                "stocks": [],
                "capital": 0.0,
                "cash_balance": full_pocket,
                "withdrawn": round(exited_value, 2),
                "reinvested": 0.0,
            }

        # 3. Normal exit: withdraw requested amount to pocket, reinvest remainder
        withdraw = min(max(float(withdraw_amount), 0.0), exited_value)
        reinvest = exited_value - withdraw
        new_capital = max(capital - withdraw, 0.0)
        new_cash_balance = float(p.cash_balance or 0.0) + withdraw

        # 4. Normalize remaining stock weights by total remaining weight sum
        total_remaining_weight = sum(weight_map.get(t, 0.0) for t in remaining)
        normalized_weights = {}
        new_allocations = {}

        if total_remaining_weight > 0:
            for t in remaining:
                norm_w = weight_map.get(t, 0.0) / total_remaining_weight
                normalized_weights[t] = norm_w
                current_alloc = allocation_map.get(t, weight_map.get(t, 0.0) * capital)
                # Invest reinvested amount in that proportion
                new_allocations[t] = current_alloc + (reinvest * norm_w)
        else:
            eq_w = 1.0 / len(remaining)
            for t in remaining:
                normalized_weights[t] = eq_w
                new_allocations[t] = new_capital * eq_w

        # 5. Update portfolio state without triggering retraining
        p.stocks = remaining
        p.capital = new_capital
        p.cash_balance = new_cash_balance
        p.status = "active"
        p.model_trained = True

        now = datetime.now(timezone.utc)
        wh = WeightHistory(
            portfolio_id=p.id,
            date=now,
            weights={t: round(normalized_weights[t], 6) for t in remaining},
            allocations={t: round(new_allocations[t], 2) for t in remaining},
        )
        db.add(wh)

        _log_transaction(db, p.id, "exit_stock", {
            "ticker": ticker,
            "exited_value": exited_value,
            "withdrawn_to_pocket": withdraw,
            "reinvested": reinvest,
            "remaining": remaining,
            "new_weights": {t: round(normalized_weights[t], 6) for t in remaining},
            "new_allocations": {t: round(new_allocations[t], 2) for t in remaining},
        })
        db.commit()

    return {
        "message": f"Exited {ticker}. Withdrawn amount moved to pocket; remainder reinvested in remaining stocks proportionally.",
        "stocks": remaining,
        "capital": new_capital,
        "cash_balance": new_cash_balance,
        "withdrawn": round(withdraw, 2),
        "reinvested": round(reinvest, 2),
    }


async def reinvest_from_pocket(portfolio_id: str, user_id: str, amount: float) -> Dict:
    """
    Take `amount` INR from the pocket (cash_balance) and distribute it across
    current holdings in proportion to their latest trained model weights.

    Steps:
    1. Validate: amount <= cash_balance, portfolio has stocks.
    2. Fetch latest weight snapshot from WeightHistory (or ml_service if stale).
    3. Normalize weights for current stocks (subset of model universe).
    4. For each stock: new_allocation = old_allocation + amount * normalized_weight
    5. Deduct amount from cash_balance, add to capital.
    6. Persist new WeightHistory snapshot.
    """
    amount = float(amount)

    with get_db_session() as db:
        p = _get_portfolio_or_raise(db, portfolio_id, user_id)
        stocks = list(p.stocks or [])

        if not stocks:
            raise ValueError("Portfolio has no holdings to reinvest into.")

        cash_balance = float(p.cash_balance or 0.0)
        if amount > cash_balance + 1e-6:
            raise ValueError(
                f"Requested reinvestment ₹{amount:,.2f} exceeds pocket balance ₹{cash_balance:,.2f}."
            )

        reinvest_amount = min(amount, cash_balance)
        capital = float(p.capital)

        # 1. Fetch current weight map from latest WeightHistory
        latest_wh = (
            db.query(WeightHistory)
            .filter(WeightHistory.portfolio_id == p.id)
            .order_by(desc(WeightHistory.date))
            .first()
        )

        if latest_wh and latest_wh.weights and set(stocks).issubset(set(latest_wh.weights.keys())):
            weight_map = {t: float(latest_wh.weights.get(t, 0.0)) for t in stocks}
            alloc_map = {
                t: float(latest_wh.allocations.get(t, weight_map.get(t, 0.0) * capital))
                for t in stocks
            }
        else:
            # Fallback: fetch from ml_service
            allocations_raw, _ = await ml_service.get_weights(stocks, capital)
            weight_map = {a["ticker"]: float(a["weight"]) for a in allocations_raw}
            alloc_map = {a["ticker"]: float(a["allocation_inr"]) for a in allocations_raw}

        # 2. Normalize weights to sum to 1 (handles subset of model universe)
        total_weight = sum(weight_map.get(t, 0.0) for t in stocks)
        if total_weight <= 0:
            # Equal-weight fallback if no weights available
            eq_w = 1.0 / len(stocks)
            normalized_weights = {t: eq_w for t in stocks}
        else:
            normalized_weights = {t: weight_map.get(t, 0.0) / total_weight for t in stocks}

        # 3. Distribute reinvest_amount proportionally
        new_alloc_map = {
            t: alloc_map.get(t, 0.0) + reinvest_amount * normalized_weights[t]
            for t in stocks
        }

        # 4. New capital and cash_balance
        new_capital = capital + reinvest_amount
        new_cash_balance = cash_balance - reinvest_amount

        # 5. Persist
        p.capital = new_capital
        p.cash_balance = new_cash_balance

        now = datetime.now(timezone.utc)
        wh = WeightHistory(
            portfolio_id=p.id,
            date=now,
            weights={t: round(normalized_weights[t], 6) for t in stocks},
            allocations={t: round(new_alloc_map[t], 2) for t in stocks},
        )
        db.add(wh)

        _log_transaction(db, p.id, "reinvest_from_pocket", {
            "amount_reinvested": round(reinvest_amount, 2),
            "new_capital": round(new_capital, 2),
            "new_cash_balance": round(new_cash_balance, 2),
            "distribution": {t: round(reinvest_amount * normalized_weights[t], 2) for t in stocks},
        })
        db.commit()

    return {
        "message": f"Successfully reinvested ₹{reinvest_amount:,.2f} from pocket into {len(stocks)} holdings.",
        "amount_reinvested": round(reinvest_amount, 2),
        "capital": round(new_capital, 2),
        "cash_balance": round(new_cash_balance, 2),
        "allocations": [
            {
                "ticker": t,
                "weight": round(normalized_weights[t], 6),
                "allocation_inr": round(new_alloc_map[t], 2),
                "added_inr": round(reinvest_amount * normalized_weights[t], 2),
            }
            for t in stocks
        ],
    }


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

async def get_weights(portfolio_id: str, user_id: str) -> Dict:
    """Return latest portfolio weights + ₹ allocations and persist snapshot in PostgreSQL."""
    with get_db_session() as db:
        p = _get_portfolio_or_raise(db, portfolio_id, user_id)
        stocks = list(p.stocks or [])
        capital = float(p.capital)
        current_status = p.status
        is_model_trained = p.model_trained

        if not stocks:
            return {
                "portfolio_id": portfolio_id,
                "date": datetime.now(timezone.utc),
                "capital": capital,
                "allocations": [],
                "model_trained": False,
                "status": current_status or "idle",
            }

        # Check if latest WeightHistory matches current stocks universe and is not equal-weights dummy fallback
        latest_wh = (
            db.query(WeightHistory)
            .filter(WeightHistory.portfolio_id == p.id)
            .order_by(desc(WeightHistory.date))
            .first()
        )
        is_equal_fallback = bool(
            latest_wh and latest_wh.weights and len(stocks) > 1 and
            all(abs(float(latest_wh.weights.get(t, 0.0)) - 1.0/len(stocks)) < 1e-4 for t in stocks)
        )
        if latest_wh and latest_wh.weights and set(latest_wh.weights.keys()) == set(stocks) and not is_equal_fallback:
            allocations = [
                {
                    "ticker": t,
                    "weight": round(float(latest_wh.weights[t]), 6),
                    "allocation_inr": round(float(latest_wh.allocations.get(t, float(latest_wh.weights[t]) * capital)), 2),
                }
                for t in stocks
            ]
            effective_trained = is_model_trained or True
            return {
                "portfolio_id": portfolio_id,
                "date": latest_wh.date or datetime.now(timezone.utc),
                "capital": capital,
                "allocations": allocations,
                "model_trained": effective_trained,
                "status": "active" if effective_trained else current_status,
            }

    allocations, model_trained = await ml_service.get_weights(stocks, capital)

    weights_dict = {a["ticker"]: a["weight"] for a in allocations}
    allocation_dict = {a["ticker"]: a["allocation_inr"] for a in allocations}
    now = datetime.now(timezone.utc)

    with get_db_session() as db:
        p = _get_portfolio_or_raise(db, portfolio_id, user_id)
        wh = WeightHistory(
            portfolio_id=p.id,
            date=now,
            weights=weights_dict,
            allocations=allocation_dict,
        )
        db.add(wh)

        if model_trained and not p.model_trained:
            p.model_trained = True
            p.status = "active"
        db.commit()

    effective_trained = model_trained or is_model_trained
    return {
        "portfolio_id": portfolio_id,
        "date": now,
        "capital": capital,
        "allocations": allocations,
        "model_trained": effective_trained,
        "status": "active" if effective_trained else current_status,
    }


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

async def get_performance(portfolio_id: str, user_id: str) -> Dict:
    with get_db_session() as db:
        p = _get_portfolio_or_raise(db, portfolio_id, user_id)
        stocks = list(p.stocks or [])

    perf = await ml_service.compute_performance(stocks)
    return {"portfolio_id": portfolio_id, **perf}


# ---------------------------------------------------------------------------
# Rebalance
# ---------------------------------------------------------------------------

async def rebalance(portfolio_id: str, user_id: str) -> Dict:
    """
    Force a rebalance cycle in PostgreSQL:
    1. Retrain model
    2. Fetch new weights
    3. Compute turnover vs last weights
    4. Apply transaction cost
    5. Persist RebalanceHistory, WeightHistory, and Transaction in PostgreSQL
    """
    with get_db_session() as db:
        p = _get_portfolio_or_raise(db, portfolio_id, user_id)
        stocks = list(p.stocks or [])
        capital = float(p.capital)

        # Get old weights from latest history
        latest_wh = (
            db.query(WeightHistory)
            .filter(WeightHistory.portfolio_id == p.id)
            .order_by(desc(WeightHistory.date))
            .first()
        )
        old_weights = (
            latest_wh.weights if latest_wh and latest_wh.weights
            else {t: 1 / len(stocks) for t in stocks} if stocks else {}
        )

    # Retrain and get new weights
    await ml_service.train_now(stocks)
    allocations, model_trained = await ml_service.get_weights(stocks, capital)
    new_weights = {a["ticker"]: a["weight"] for a in allocations}

    # Turnover
    all_tickers = set(old_weights) | set(new_weights)
    turnover = sum(
        abs(new_weights.get(t, 0.0) - old_weights.get(t, 0.0))
        for t in all_tickers
    )
    cost_inr = turnover * float(os.getenv("COST_RATE", "0.001")) * capital
    now = datetime.now(timezone.utc)

    # Persist in PostgreSQL
    with get_db_session() as db:
        p = _get_portfolio_or_raise(db, portfolio_id, user_id)
        p.last_rebalanced = now
        p.model_trained = model_trained
        p.status = "active"

        reb = RebalanceHistory(
            portfolio_id=p.id,
            date=now,
            old_weights=old_weights,
            new_weights=new_weights,
            turnover=float(turnover),
            transaction_cost=float(cost_inr / capital) if capital > 0 else 0.0,
        )
        db.add(reb)

        wh = WeightHistory(
            portfolio_id=p.id,
            date=now,
            weights=new_weights,
            allocations={a["ticker"]: a["allocation_inr"] for a in allocations},
        )
        db.add(wh)

        _log_transaction(db, p.id, "rebalance", {
            "turnover": turnover,
            "cost_inr": cost_inr,
        })
        db.commit()

    return {
        "message": "Rebalance complete",
        "date": now,
        "allocations": allocations,
        "turnover": round(turnover, 6),
        "transaction_cost_inr": round(cost_inr, 2),
    }


# ---------------------------------------------------------------------------
# Update capital
# ---------------------------------------------------------------------------

async def update_capital(portfolio_id: str, user_id: str, capital: float) -> Dict:
    with get_db_session() as db:
        p = _get_portfolio_or_raise(db, portfolio_id, user_id)
        p.capital = float(capital)
        db.commit()
    return {"message": "Capital updated", "capital": capital}

"""
Pydantic v2 schemas for API requests and responses (PostgreSQL-backed).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserInDB(BaseModel):
    id: Optional[Union[str, int]] = None
    email: EmailStr
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class UserOut(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

class PortfolioCreate(BaseModel):
    name: str = "My Portfolio"
    stocks: List[str] = Field(default_factory=list)
    capital: float = Field(gt=0, description="Total capital in ₹")


class PortfolioInDB(BaseModel):
    id: Optional[Union[str, int]] = None
    user_id: Optional[Union[str, int]] = None
    name: str
    stocks: List[str]
    capital: float
    cash_balance: float = 0.0
    status: str = "active"        # active | training | error
    model_trained: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_rebalanced: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class PortfolioOut(BaseModel):
    id: str
    name: str
    stocks: List[str]
    capital: float
    cash_balance: float = 0.0
    status: str
    model_trained: bool
    created_at: datetime
    last_rebalanced: Optional[datetime]


# ---------------------------------------------------------------------------
# Stock operations
# ---------------------------------------------------------------------------

class AddStockRequest(BaseModel):
    portfolio_id: str
    ticker: str = Field(min_length=1, max_length=20)


class AddStocksRequest(BaseModel):
    portfolio_id: str
    tickers: List[str] = Field(default_factory=list)


class RemoveStockRequest(BaseModel):
    portfolio_id: str
    ticker: str


class ExitStockRequest(BaseModel):
    portfolio_id: str
    ticker: str
    withdraw_amount: float = Field(default=0, ge=0)


class ReinvestFromPocketRequest(BaseModel):
    portfolio_id: str
    amount: float = Field(gt=0, description="Amount in INR to reinvest from pocket into current holdings")


# ---------------------------------------------------------------------------
# Weights / Allocation
# ---------------------------------------------------------------------------

class StockAllocation(BaseModel):
    ticker: str
    weight: float
    allocation_inr: float


class WeightsResponse(BaseModel):
    portfolio_id: str
    date: datetime
    capital: float
    allocations: List[StockAllocation]
    model_trained: bool
    status: str


class WeightHistoryEntry(BaseModel):
    id: Optional[Union[str, int]] = None
    portfolio_id: str
    date: datetime
    weights: Dict[str, float]          # {ticker: weight}
    allocations: Dict[str, float]      # {ticker: ₹ amount}
    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

class PerformanceMetrics(BaseModel):
    sharpe: float
    arithmetic_return: float
    geometric_return: float
    volatility: float
    max_drawdown: float
    avg_turnover: float
    cost_drag: float


class TimeSeriesPoint(BaseModel):
    date: str
    value: float


class PerformanceResponse(BaseModel):
    portfolio_id: str
    metrics: PerformanceMetrics
    wealth_spt: List[TimeSeriesPoint]
    wealth_market: List[TimeSeriesPoint]
    wealth_net: List[TimeSeriesPoint]
    relative_wealth: List[TimeSeriesPoint]
    turnover: List[TimeSeriesPoint]
    weights_history: List[Dict[str, Any]]   # [{date, ticker: weight}]


# ---------------------------------------------------------------------------
# Rebalance
# ---------------------------------------------------------------------------

class RebalanceRecord(BaseModel):
    id: Optional[Union[str, int]] = None
    portfolio_id: str
    date: datetime
    old_weights: Dict[str, float]
    new_weights: Dict[str, float]
    turnover: float
    transaction_cost: float
    sharpe_before: Optional[float] = None
    sharpe_after: Optional[float] = None
    model_config = {"populate_by_name": True}


class RebalanceResponse(BaseModel):
    message: str
    date: datetime
    allocations: List[StockAllocation]
    turnover: float
    transaction_cost_inr: float
    metrics: Optional[PerformanceMetrics] = None


# ---------------------------------------------------------------------------
# Model metrics
# ---------------------------------------------------------------------------

class ModelMetricsRecord(BaseModel):
    id: Optional[Union[str, int]] = None
    portfolio_id: str
    date: datetime
    sharpe_gross: float
    sharpe_net: float
    annual_return: float
    volatility: float
    max_drawdown: float
    training_duration_s: float
    epochs: int
    model_config = {"populate_by_name": True}


class ModelStatusResponse(BaseModel):
    status: str          # idle | training | done | error
    last_trained: Optional[datetime]
    last_metrics: Optional[Dict[str, Any]]
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------

class TransactionRecord(BaseModel):
    id: Optional[Union[str, int]] = None
    portfolio_id: str
    date: datetime
    type: str            # add_stock | remove_stock | rebalance | create
    details: Dict[str, Any]
    model_config = {"populate_by_name": True}

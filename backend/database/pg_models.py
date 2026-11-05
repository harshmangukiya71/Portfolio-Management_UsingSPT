"""
SQLAlchemy ORM models for PostgreSQL database.
Enables viewing, modifying, and querying full project entities in pgAdmin.
"""

from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship
from backend.database.postgres import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="user", nullable=False)  # "admin" or "user" for RBAC
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    portfolios = relationship("Portfolio", back_populates="owner", cascade="all, delete-orphan")


class Portfolio(Base):
    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    name = Column(String(100), default="My Portfolio", nullable=False)
    stocks = Column(JSON, nullable=False, default=list)  # List of ticker strings: ["RELIANCE.NS", "TCS.NS"]
    capital = Column(Float, nullable=False, default=100000.0)
    cash_balance = Column(Float, default=0.0)
    status = Column(String(50), default="active")  # active | training | error
    model_trained = Column(Boolean, default=False)
    last_rebalanced = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="portfolios")
    weights = relationship("WeightHistory", back_populates="portfolio", cascade="all, delete-orphan")
    rebalances = relationship("RebalanceHistory", back_populates="portfolio", cascade="all, delete-orphan")
    metrics = relationship("ModelMetrics", back_populates="portfolio", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="portfolio", cascade="all, delete-orphan")


class WeightHistory(Base):
    __tablename__ = "weights_history"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), index=True, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    weights = Column(JSON, nullable=False)  # {"RELIANCE.NS": 0.4, "TCS.NS": 0.6}
    allocations = Column(JSON, nullable=False)  # {"RELIANCE.NS": 40000.0, "TCS.NS": 60000.0}

    portfolio = relationship("Portfolio", back_populates="weights")


class RebalanceHistory(Base):
    __tablename__ = "rebalance_history"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), index=True, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    old_weights = Column(JSON, nullable=False)
    new_weights = Column(JSON, nullable=False)
    turnover = Column(Float, default=0.0)
    transaction_cost = Column(Float, default=0.0)
    sharpe_before = Column(Float, nullable=True)
    sharpe_after = Column(Float, nullable=True)

    portfolio = relationship("Portfolio", back_populates="rebalances")


class ModelMetrics(Base):
    __tablename__ = "model_metrics"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), index=True, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    sharpe_gross = Column(Float, default=0.0)
    sharpe_net = Column(Float, default=0.0)
    annual_return = Column(Float, default=0.0)
    volatility = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    training_duration_s = Column(Float, default=0.0)
    epochs = Column(Integer, default=50)

    portfolio = relationship("Portfolio", back_populates="metrics")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), index=True, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    type = Column(String(50), nullable=False)  # create, rebalance, add_stock, remove_stock
    details = Column(JSON, nullable=True)

    portfolio = relationship("Portfolio", back_populates="transactions")


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

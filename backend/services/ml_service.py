"""
ML Service — thin async wrapper around the existing src/ ML pipeline.

Responsibilities:
- Manage FunctionalSPT model lifecycle (load / retrain / infer)
- Run feature engineering and backtest for performance metrics
- Expose training status for API polling
- All heavy computation runs in a thread pool (non-blocking)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch

# ── Ensure src/ is importable from backend/ ────────────────────────────────
_ROOT = Path(__file__).parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.data.downloader import download_prices
from src.data.features import build_features_functional_spt
from src.models.functional_spt import FunctionalSPT
from src.portfolio.rebalancing import apply_rebalancing_functional
from src.portfolio.transaction_cost import apply_transaction_cost
from src.training.evaluate import compute_metrics, growth_of_one
from src.training.losses import improved_objective, smoothness_penalty
from src.training.trainer import Trainer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config from env
# ---------------------------------------------------------------------------

CHECKPOINT_DIR    = os.getenv("CHECKPOINT_DIR", "checkpoints")
START_DATE        = os.getenv("MODEL_START_DATE", "2005-01-01")
SPLIT_DATE        = os.getenv("MODEL_SPLIT_DATE", "2020-01-01")
SKIP_GARCH        = os.getenv("SKIP_GARCH", "false").lower() == "true"
COST_RATE         = float(os.getenv("COST_RATE", "0.001"))
VOL_TARGET        = float(os.getenv("VOL_TARGET", "0.15"))
HOLDING_DAYS      = int(os.getenv("REBALANCE_DAYS", "21"))
GARCH_PENALTY     = 0.3

_executor = ThreadPoolExecutor(max_workers=2)


# ---------------------------------------------------------------------------
# Singleton ML service state
# ---------------------------------------------------------------------------

class _MLState:
    """Thread-safe(ish) singleton holding model + training state."""

    def __init__(self):
        self.model: Optional[FunctionalSPT] = None
        self.model_stocks: List[str] = []
        self.status: str = "idle"   # idle | training | done | error
        self.error: Optional[str] = None
        self.last_trained: Optional[datetime] = None
        self.last_metrics: Dict[str, Any] = {}
        self.last_performance: Optional[Dict[str, Any]] = None
        self._lock = asyncio.Lock()

_state = _MLState()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_status() -> Dict[str, Any]:
    return {
        "status":       _state.status,
        "last_trained": _state.last_trained,
        "last_metrics": _state.last_metrics,
        "error":        _state.error,
    }


async def get_weights(
    stocks: List[str],
    capital: float,
) -> Tuple[List[Dict], bool]:
    """
    Return portfolio weights + ₹ allocations for `stocks`.

    If stocks is empty (fully liquidated portfolio) returns ([], False) immediately.
    If no model is trained for these exact stocks, returns equal weights
    and triggers background retraining.

    Returns
    -------
    (allocations, model_was_trained)
    """
    # ── Guard: nothing to do for an empty portfolio ─────────────────────
    if not stocks:
        return [], False

    if _state.model is None:
        load_checkpoint_if_exists()

    # If model matches stocks or trained universe is a superset of stocks → run inference
    if _state.model is not None and (set(stocks).issubset(set(_state.model_stocks)) or set(stocks) == set(_state.model_stocks)):
        full_weights = await _run_inference(_state.model_stocks if _state.model_stocks else stocks)
        sub_weights = {t: full_weights.get(t, 0.0) for t in stocks}
        total_sub = sum(sub_weights.values())
        if total_sub > 0:
            weights_dict = {t: sub_weights[t] / total_sub for t in stocks}
        else:
            n = len(stocks)
            weights_dict = {t: 1.0 / n for t in stocks}
        trained = True
    elif _state.model is not None and _state.model_stocks:
        # Model is available for another universe; run inference on model_stocks and project/normalize
        full_weights = await _run_inference(_state.model_stocks)
        matching = [t for t in stocks if t in full_weights]
        if matching:
            sub_weights = {t: full_weights.get(t, 0.0) for t in stocks}
            total_sub = sum(sub_weights.values())
            weights_dict = {t: (sub_weights[t] / total_sub if total_sub > 0 else 1.0 / len(stocks)) for t in stocks}
            trained = True
        else:
            n = len(stocks)
            weights_dict = {t: 1.0 / n for t in stocks}
            trained = False
            asyncio.create_task(_background_retrain(stocks))
    else:
        # Fallback: equal weights only if no model checkpoint exists anywhere
        n = len(stocks)
        weights_dict = {t: 1.0 / n for t in stocks}
        trained = False
        logger.info("No matching model — using equal weights; scheduling retrain")
        asyncio.create_task(_background_retrain(stocks))

    allocations = [
        {
            "ticker":         ticker,
            "weight":         round(w, 6),
            "allocation_inr": round(w * capital, 2),
        }
        for ticker, w in weights_dict.items()
    ]
    return allocations, trained


async def retrain(stocks: List[str]) -> None:
    """Trigger model retraining (returns immediately; runs in background)."""
    if not stocks:
        logger.info("retrain called with empty stock list — skipping")
        return
    asyncio.create_task(_background_retrain(stocks))


async def train_now(stocks: List[str]) -> Dict[str, Any]:
    """Train immediately and return the completed training metrics."""
    if not stocks:
        logger.info("train_now called with empty stock list — skipping")
        return {}
    await _background_retrain(stocks)
    if _state.status == "error":
        raise RuntimeError(_state.error or "Training failed")
    return _state.last_metrics


async def compute_performance(
    stocks: List[str],
) -> Dict[str, Any]:
    """
    Run full backtest for `stocks` and return metrics + time series.
    Blocking — runs in thread pool.
    """
    if not stocks:
        return {
            "metrics": {
                "sharpe_net": 0.0,
                "annual_return": 0.0,
                "volatility": 0.0,
                "max_drawdown": 0.0,
                "avg_turnover": 0.0,
                "cost_drag": 0.0
            },
            "wealth_index": {}
        }
    if _state.last_performance and set(_state.last_performance.get("stocks", [])) == set(stocks):
        return _state.last_performance["data"]

    loop = asyncio.get_event_loop()
    res = await loop.run_in_executor(
        _executor, _compute_performance_sync, stocks
    )
    _state.last_performance = {"stocks": list(stocks), "data": res}
    return res

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _run_inference(stocks: List[str]) -> Dict[str, float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _inference_sync, stocks)


def _inference_sync(stocks: List[str]) -> Dict[str, float]:
    """Fetch recent data and compute a forward-pass weight vector."""
    try:
        prices = download_prices(
            stocks=stocks,
            start=SPLIT_DATE,
            cache_dir="data/cache",
            force_refresh=False,
        )
        feat = build_features_functional_spt(
            prices=prices,
            use_garch=(not SKIP_GARCH),
        )
        x = feat["x"]
        garch = feat["garch_rank"]

        # Use last available day
        x_last     = torch.tensor(x.iloc[[-1]].values,     dtype=torch.float32)
        garch_last = torch.tensor(garch.iloc[[-1]].values, dtype=torch.float32)

        with torch.no_grad():
            w = _state.model(x_last, garch_last).numpy()[0]

        # Re-index to ordered stocks
        cols = list(x.columns)
        return {t: float(w[i]) for i, t in enumerate(cols) if t in stocks}

    except Exception as exc:
        logger.exception("Inference failed: %s", exc)
        n = len(stocks)
        return {t: 1.0 / n for t in stocks}


async def _background_retrain(stocks: List[str]) -> None:
    """Async wrapper for blocking retrain — sets state accordingly."""
    # ── Guard: never train on an empty universe ──────────────────────────
    if not stocks:
        logger.info("_background_retrain called with empty stock list — setting idle")
        async with _state._lock:
            _state.status = "idle"
            _state.error  = None
        return

    async with _state._lock:
        if _state.status == "training":
            logger.info("Retrain already in progress — skipping")
            return
        _state.status = "training"
        _state.error  = None

    loop = asyncio.get_event_loop()
    try:
        model, metrics = await loop.run_in_executor(
            _executor, _train_sync, stocks
        )
        async with _state._lock:
            _state.model        = model
            _state.model_stocks = list(stocks)
            _state.status       = "done"
            _state.last_trained = datetime.utcnow()
            _state.last_metrics = metrics
            _state.last_performance = None
        logger.info("Retrain complete | Sharpe(net)=%.4f", metrics.get("sharpe_net", 0))

        try:
            import json
            meta_path = Path(CHECKPOINT_DIR) / "model_meta.json"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump({
                    "stocks": list(stocks),
                    "metrics": metrics,
                    "saved_at": datetime.utcnow().isoformat(),
                }, f, indent=2)
        except Exception as meta_err:
            logger.warning("Could not save model metadata: %s", meta_err)

        try:
            from backend.database.postgres import get_db_session
            from backend.database.pg_models import Portfolio, WeightHistory
            with get_db_session() as db:
                p = db.query(Portfolio).first()
                if p:
                    p.model_trained = True
                    p.status = "active"
                    w_inferred = _inference_sync(list(stocks))
                    cap = float(p.capital)
                    wh = WeightHistory(
                        portfolio_id=p.id,
                        date=datetime.utcnow(),
                        weights={t: round(w_inferred.get(t, 1.0/len(stocks)), 6) for t in stocks},
                        allocations={t: round(w_inferred.get(t, 1.0/len(stocks)) * cap, 2) for t in stocks},
                    )
                    db.add(wh)
                    db.commit()
        except Exception as db_err:
            logger.warning("Could not update Portfolio/WeightHistory in PostgreSQL: %s", db_err)

    except Exception as exc:
        async with _state._lock:
            _state.status = "error"
            _state.error  = str(exc)
        logger.exception("Retrain failed: %s", exc)


def _train_sync(stocks: List[str]) -> Tuple[FunctionalSPT, Dict]:
    """Full training pipeline — runs synchronously in thread pool."""
    t0 = time.time()

    # ── Data ────────────────────────────────────────────────────────────────
    prices = download_prices(
        stocks=stocks,
        start=START_DATE,
        cache_dir="data/cache",
        force_refresh=False,
    )

    # ── Features ────────────────────────────────────────────────────────────
    feat = build_features_functional_spt(
        prices=prices,
        use_garch=(not SKIP_GARCH),
    )
    x, returns, mu, garch_rank = (
        feat["x"], feat["returns"], feat["mu"], feat["garch_rank"]
    )

    split = SPLIT_DATE
    x_train, x_test         = x.loc[:split], x.loc[split:]
    ret_train, ret_test     = returns.loc[:split], returns.loc[split:]
    mu_train, mu_test       = mu.loc[:split], mu.loc[split:]
    garch_train, garch_test = garch_rank.loc[:split], garch_rank.loc[split:]

    x_train_t     = torch.tensor(x_train.values,     dtype=torch.float32)
    ret_train_t   = torch.tensor(ret_train.values,   dtype=torch.float32)
    mu_train_t    = torch.tensor(mu_train.values,    dtype=torch.float32)
    garch_train_t = torch.tensor(garch_train.values, dtype=torch.float32)

    # ── Model ────────────────────────────────────────────────────────────────
    model = FunctionalSPT(hidden_dim=32, output_dim=16, garch_penalty=GARCH_PENALTY)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
        optimizer, T_0=200, T_mult=2, eta_min=1e-5
    )
    trainer = Trainer(
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        patience=200,
        checkpoint_dir=CHECKPOINT_DIR,
        model_name="functional_spt",
    )

    gamma, sharpe_lambda, lam_smooth = 3.0, 0.5, 3.0

    def loss_fn():
        w = model(x_train_t, garch_train_t)
        obj = improved_objective(w, ret_train_t, mu_train_t,
                                 gamma=gamma, sharpe_lambda=sharpe_lambda)
        smooth = smoothness_penalty(model, x_train_t)
        return -obj + lam_smooth * smooth

    def monitor_fn():
        w = model(x_train_t, garch_train_t)
        obj = improved_objective(w, ret_train_t, mu_train_t,
                                 gamma=gamma, sharpe_lambda=sharpe_lambda)
        return float(obj.item())

    result = trainer.train(
        epochs=2000,
        loss_fn=loss_fn,
        monitor_fn=monitor_fn,
        log_every=200,
        checkpoint_meta={"hidden_dim": 32, "output_dim": 16},
    )

    # ── Evaluate ─────────────────────────────────────────────────────────────
    model.eval()
    comparison, final_weights = apply_rebalancing_functional(
        model=model,
        x_data=x_test,
        returns_data=ret_test,
        market_weights=mu_test,
        garch_data=garch_test,
        holding_days=HOLDING_DAYS,
        vol_target=VOL_TARGET,
    )
    net_spt, turnover = apply_transaction_cost(
        portfolio_returns=comparison["Functional SPT"],
        weights=final_weights,
        cost_rate=COST_RATE,
        holding_days=HOLDING_DAYS,
    )
    comparison["Functional SPT (After Cost)"] = net_spt
    comparison = comparison.dropna()

    metrics_df = compute_metrics(comparison)
    row        = metrics_df.loc["Functional SPT (After Cost)"]
    mkt        = metrics_df.loc["Market"]

    elapsed = time.time() - t0
    metrics = {
        "sharpe_net":    float(row["Sharpe"]),
        "sharpe_gross":  float(metrics_df.loc["Functional SPT", "Sharpe"]),
        "sharpe_market": float(mkt["Sharpe"]),
        "annual_return": float(row["Arithmetic Return"]),
        "volatility":    float(row["Volatility"]),
        "max_drawdown":  float(row["Max Drawdown"]),
        "avg_turnover":  float(turnover.mean()),
        "training_s":    elapsed,
        "best_epoch":    result["best_epoch"],
    }
    return model, metrics


def _compute_performance_sync(stocks: List[str]) -> Dict[str, Any]:
    """Full backtest — returns dict with metrics + time series."""
    try:
        prices = download_prices(
            stocks=stocks,
            start=SPLIT_DATE,
            cache_dir="data/cache",
            force_refresh=False,
        )
        feat = build_features_functional_spt(
            prices=prices,
            use_garch=(not SKIP_GARCH),
        )
        x, returns, mu, garch_rank = (
            feat["x"], feat["returns"], feat["mu"], feat["garch_rank"]
        )

        if _state.model is None:
            # No model trained yet → return empty/fallback
            return _empty_performance(stocks)

        comparison, final_weights = apply_rebalancing_functional(
            model=_state.model,
            x_data=x,
            returns_data=returns,
            market_weights=mu,
            garch_data=garch_rank,
            holding_days=HOLDING_DAYS,
            vol_target=VOL_TARGET,
        )
        net_spt, turnover = apply_transaction_cost(
            portfolio_returns=comparison["Functional SPT"],
            weights=final_weights,
            cost_rate=COST_RATE,
            holding_days=HOLDING_DAYS,
        )
        comparison["Functional SPT (After Cost)"] = net_spt
        comparison = comparison.dropna()

        wealth = growth_of_one(comparison)
        metrics_df = compute_metrics(comparison)
        row = metrics_df.loc["Functional SPT (After Cost)"]

        def _ts(series: pd.Series) -> List[Dict]:
            return [
                {"date": str(d.date()), "value": round(float(v), 6)}
                for d, v in series.items()
            ]

        def _weights_ts(weights_df: pd.DataFrame) -> List[Dict]:
            out = []
            for date, row_w in weights_df.iterrows():
                entry = {"date": str(date.date())}
                entry.update({c: round(float(v), 6) for c, v in row_w.items()})
                out.append(entry)
            return out

        return {
            "metrics": {
                "sharpe":            float(row["Sharpe"]),
                "arithmetic_return": float(row["Arithmetic Return"]),
                "geometric_return":  float(row["Geometric Return"]),
                "volatility":        float(row["Volatility"]),
                "max_drawdown":      float(row["Max Drawdown"]),
                "avg_turnover":      float(turnover.mean()),
                "cost_drag":         float(
                    wealth["Functional SPT"].iloc[-1]
                    - wealth["Functional SPT (After Cost)"].iloc[-1]
                ),
            },
            "wealth_spt":      _ts(wealth["Functional SPT"]),
            "wealth_market":   _ts(wealth["Market"]),
            "wealth_net":      _ts(wealth["Functional SPT (After Cost)"]),
            "relative_wealth": _ts(wealth["Functional SPT (After Cost)"] / wealth["Market"]),
            "turnover":        _ts(turnover),
            "weights_history": _weights_ts(final_weights.iloc[::HOLDING_DAYS]),
        }

    except Exception as exc:
        logger.exception("Performance computation failed: %s", exc)
        return _empty_performance(stocks)


def _empty_performance(stocks: List[str]) -> Dict[str, Any]:
    return {
        "metrics": {
            "sharpe": 0.0, "arithmetic_return": 0.0, "geometric_return": 0.0,
            "volatility": 0.0, "max_drawdown": 0.0, "avg_turnover": 0.0, "cost_drag": 0.0,
        },
        "wealth_spt": [], "wealth_market": [], "wealth_net": [],
        "relative_wealth": [], "turnover": [], "weights_history": [],
    }


def load_checkpoint_if_exists() -> None:
    """Called on startup — loads the most recent checkpoint if available."""
    import json
    ckpt_dir = Path(CHECKPOINT_DIR)
    path = ckpt_dir / "functional_spt_best.pt"
    meta_path = ckpt_dir / "model_meta.json"
    if path.exists():
        try:
            _state.model = FunctionalSPT.load(str(path))
            _state.status = "done"
            _state.last_trained = datetime.utcnow()
            logger.info("Loaded model checkpoint ← %s", path)

            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    _state.model_stocks = meta.get("stocks", [])
                    _state.last_metrics = meta.get("metrics", {})
                    logger.info("Restored model metadata: stocks=%s", _state.model_stocks)
                except Exception as meta_exc:
                    logger.warning("Could not read %s: %s", meta_path, meta_exc)

            if not _state.model_stocks:
                try:
                    from backend.database.postgres import get_db_session
                    from backend.database.pg_models import Portfolio
                    with get_db_session() as db:
                        p = db.query(Portfolio).filter(Portfolio.model_trained == True).first()
                        if not p:
                            p = db.query(Portfolio).first()
                        if p and p.stocks:
                            _state.model_stocks = list(p.stocks)
                            logger.info("Restored model_stocks from PostgreSQL Portfolio #%s: %s", p.id, _state.model_stocks)
                except Exception as db_exc:
                    logger.warning("Could not restore model_stocks from PostgreSQL: %s", db_exc)
        except Exception as exc:
            logger.warning("Could not load checkpoint %s: %s", path, exc)
    else:
        logger.info("No checkpoint found at %s — model will train on first request", path)

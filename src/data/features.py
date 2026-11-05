"""
Feature engineering for both portfolio models.
All functions are pure (no side effects) for testability.
"""

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# =============================================================
# Shared helpers
# =============================================================

def compute_rsi(prices: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """
    Relative Strength Index (RSI) as a 0–1 normalized signal.
    RSI close to 1 → strongly overbought.
    """
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = -delta.clip(upper=0).rolling(window).mean()
    rs = gain / (loss + 1e-8)
    return 1 - (1 / (1 + rs))


def compute_garch_vol(returns: pd.DataFrame, p: int = 1, q: int = 1) -> pd.DataFrame:
    """
    Fast recursive GARCH(p,q) volatility using pre-fit parameters.
    Fits params once per stock, then computes vol recursively.

    Returns
    -------
    pd.DataFrame  same shape as returns, values = daily vol (σ)
    """
    try:
        from arch import arch_model
    except ImportError:
        logger.warning("arch package not found — returning rolling std instead of GARCH")
        return returns.rolling(20).std().fillna(method="bfill")

    garch_vol = pd.DataFrame(index=returns.index, columns=returns.columns, dtype=float)

    for col in returns.columns:
        series = returns[col].dropna()
        try:
            scaled = series * 100
            model = arch_model(scaled, vol="Garch", p=p, q=q)
            res = model.fit(disp="off")
            params = res.params

            omega = params["omega"]
            alpha = params["alpha[1]"]
            beta  = params["beta[1]"]

            vals = scaled.values
            T = len(vals)
            sigma2 = np.zeros(T)
            sigma2[0] = np.var(vals[:50]) if T > 50 else np.var(vals)
            for t in range(1, T):
                sigma2[t] = omega + alpha * vals[t - 1] ** 2 + beta * sigma2[t - 1]

            sigma = np.sqrt(sigma2) / 100
            garch_vol[col] = pd.Series(sigma, index=series.index)

        except Exception as exc:
            logger.warning("GARCH failed for %s: %s — using rolling std", col, exc)
            garch_vol[col] = returns[col].rolling(20).std()

    return garch_vol.astype(float)


# =============================================================
# SPT Model Features (8 features per stock per day)
# =============================================================

def build_features_spt(prices: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build feature matrix and forward returns for the SPT CNN Ranker.

    Features (8 per stock):
        mom5, mom20, mom60 — price momentum
        vol20              — rolling volatility
        ma20, ma50         — price / moving average
        rsi14              — RSI signal
        rev5               — contrarian (mean-reversion)

    Returns
    -------
    features : MultiIndex DataFrame (date × (feature, stock))
    returns  : forward daily returns aligned to features index
    """
    logger.info("Building SPT features...")

    returns = prices.pct_change().shift(-1).dropna()
    prices  = prices.loc[returns.index]

    mom_5  = prices.pct_change(5)
    mom_20 = prices.pct_change(20)
    mom_60 = prices.pct_change(60)

    vol_20 = prices.pct_change().rolling(20).std()

    ma_20  = prices / prices.rolling(20).mean()
    ma_50  = prices / prices.rolling(50).mean()

    rsi_14 = compute_rsi(prices, window=14)
    rev_5  = -prices.pct_change(5)

    features = pd.concat(
        {
            "mom5":  mom_5,
            "mom20": mom_20,
            "mom60": mom_60,
            "vol20": vol_20,
            "ma20":  ma_20,
            "ma50":  ma_50,
            "rsi14": rsi_14,
            "rev5":  rev_5,
        },
        axis=1,
    )

    features = features.dropna()
    returns  = returns.loc[features.index]

    logger.info("SPT features: %d rows × %d feature-stock pairs", len(features), features.shape[1])
    return features, returns


def prepare_tensors_spt(
    features: pd.DataFrame,
    returns:  pd.DataFrame,
    train_end: str,
    test_start: str,
):
    """
    Cross-sectionally normalize features and split into train/test tensors.

    Returns dict with keys:
        X_train_t, R_train_t, train_dates
        X_test_t,  R_test_t,  test_dates
    """
    import torch

    def _build(X: pd.DataFrame, R: pd.DataFrame):
        X_list, R_list, dates = [], [], []
        for date in X.index:
            X_day = X.loc[date].unstack(level=0)   # (stocks, features)
            R_day = R.loc[date]

            if X_day.isnull().values.any():
                continue

            # Cross-sectional z-score per day
            X_day_std = X_day.std()
            X_day_std[X_day_std < 1e-8] = 1e-8
            X_day = (X_day - X_day.mean()) / X_day_std

            X_list.append(X_day.values)
            R_list.append(R_day.values)
            dates.append(date)

        X_np = np.array(X_list)
        R_np = np.array(R_list)
        return (
            torch.tensor(X_np, dtype=torch.float32),
            torch.tensor(R_np, dtype=torch.float32),
            dates,
        )

    X_train = features.loc[:train_end]
    R_train = returns.loc[:train_end]
    X_test  = features.loc[test_start:]
    R_test  = returns.loc[test_start:]

    X_train_t, R_train_t, train_dates = _build(X_train, R_train)
    X_test_t,  R_test_t,  test_dates  = _build(X_test,  R_test)

    logger.info(
        "Train tensors: %s | Test tensors: %s",
        tuple(X_train_t.shape),
        tuple(X_test_t.shape),
    )

    return {
        "X_train_t": X_train_t,
        "R_train_t": R_train_t,
        "train_dates": train_dates,
        "X_test_t":  X_test_t,
        "R_test_t":  R_test_t,
        "test_dates": test_dates,
    }


# =============================================================
# Functional SPT Features (rank-based)
# =============================================================

def rank_transform(df: pd.DataFrame, alpha: float = 2.0) -> pd.DataFrame:
    """Percentile rank per day raised to power alpha."""
    ranked = df.rank(axis=1, pct=True)
    return ranked ** alpha


def build_features_functional_spt(
    prices: pd.DataFrame,
    momentum_window: int = 20,
    vol_window: int = 20,
    rank_alpha: float = 2.0,
    market_weight_alpha: float = 0.5,
    use_garch: bool = True,
    garch_p: int = 1,
    garch_q: int = 1,
) -> Dict[str, pd.DataFrame]:
    """
    Build features for the Functional SPT model.

    Returns
    -------
    dict with keys: x, returns, mu (market weights), garch_rank
    All DataFrames are aligned on the same date index.
    """
    logger.info("Building Functional SPT features...")

    returns = prices.pct_change().shift(-1).dropna()
    prices  = prices.loc[returns.index]

    # Market weights (price-based proxy)
    mu = prices.div(prices.sum(axis=1), axis=0)

    # Risk-adjusted momentum
    mom      = prices.pct_change(momentum_window)
    vol      = prices.pct_change().rolling(vol_window).std()
    risk_adj = mom / (vol + 1e-8)

    # Combined rank signal
    x = (
        market_weight_alpha * rank_transform(mu, alpha=rank_alpha)
        + (1 - market_weight_alpha) * risk_adj.rank(axis=1, pct=True)
    )

    # GARCH volatility rank
    if use_garch:
        logger.info("Computing GARCH volatility (this may take a few minutes)...")
        garch_vol  = compute_garch_vol(returns, p=garch_p, q=garch_q)
        garch_rank = garch_vol.rank(axis=1, pct=True)
    else:
        logger.info("GARCH disabled — using rolling vol rank")
        garch_rank = vol.rank(axis=1, pct=True)

    # Align all on common index
    common_idx = x.dropna().index
    x          = x.loc[common_idx]
    returns    = returns.loc[common_idx]
    mu         = mu.loc[common_idx]
    garch_rank = garch_rank.loc[common_idx]

    logger.info("Functional SPT features: %d trading days", len(x))

    return {
        "x":          x,
        "returns":    returns,
        "mu":         mu,
        "garch_rank": garch_rank,
    }  
"""
Loss functions for both portfolio models.
All losses are differentiable PyTorch functions.
"""

import torch
import torch.nn as nn


def sharpe_loss(
    weights: torch.Tensor,
    returns: torch.Tensor,
    model:   nn.Module,
    l2_lambda: float = 1e-4,
    dd_lambda:  float = 0.1,
) -> torch.Tensor:
    """
    SPT Model loss: maximize Sharpe - L2 penalty - drawdown penalty.

    Parameters
    ----------
    weights    : (T, N) portfolio weights
    returns    : (T, N) forward returns
    model      : nn.Module (for L2 regularization)
    l2_lambda  : L2 regularization coefficient
    dd_lambda  : max drawdown penalty coefficient

    Returns
    -------
    scalar loss (negate Sharpe + penalties) — minimize this
    """
    Rp   = torch.sum(weights * returns, dim=1)
    mean = torch.mean(Rp)
    std  = torch.std(Rp)

    sharpe = mean / (std + 1e-8)

    # Max drawdown penalty
    cumulative  = torch.cumprod(1 + Rp, dim=0)
    rolling_max = torch.cummax(cumulative, dim=0).values
    drawdown    = (rolling_max - cumulative) / (rolling_max + 1e-8)
    max_dd      = torch.max(drawdown)

    # L2 regularization
    l2_penalty = l2_lambda * sum(torch.sum(p ** 2) for p in model.parameters())

    return -sharpe + l2_penalty + dd_lambda * max_dd


def improved_objective(
    weights:         torch.Tensor,
    returns:         torch.Tensor,
    market_weights:  torch.Tensor,
    gamma:           float = 3.0,
    sharpe_lambda:   float = 0.5,
) -> torch.Tensor:
    """
    Functional SPT objective: maximize relative log-wealth over market.

    Components:
    1. Relative log-wealth over market (SPT core)
    2. Sharpe component (risk-adjusted reward)
    3. Downside deviation penalty
    4. Concentration penalty
    5. Max-drawdown penalty

    Returns
    -------
    scalar objective — maximize this (loss = -objective)
    """
    Rp = torch.sum(weights * returns, dim=1)
    Rm = torch.sum(market_weights * returns, dim=1)

    # SPT core
    rel_growth = torch.mean(torch.log(1 + Rp) - torch.log(1 + Rm))

    # Sharpe
    sharpe = torch.mean(Rp) / (torch.std(Rp) + 1e-8)

    # Downside penalty
    downside = torch.mean(torch.clamp(Rp, max=0) ** 2)

    # Concentration
    concentration = torch.mean(torch.sum(weights ** 2, dim=1))

    # Drawdown
    cumulative  = torch.cumprod(1 + Rp, dim=0)
    rolling_max = torch.cummax(cumulative, dim=0).values
    drawdown    = (rolling_max - cumulative) / (rolling_max + 1e-8)
    max_dd      = torch.mean(drawdown ** 2)

    return (
        rel_growth
        + sharpe_lambda * sharpe
        - gamma * downside
        - 0.1 * concentration
        - 0.7 * max_dd
    )


def smoothness_penalty(model: nn.Module, x_sample: torch.Tensor) -> torch.Tensor:
    """
    Penalize curvature of f(x) — promotes a smooth, monotonic
    weight-vs-rank relationship in the Functional SPT model.

    Parameters
    ----------
    model    : FunctionalSPT instance
    x_sample : (T, N) rank input tensor

    Returns
    -------
    scalar penalty
    """
    x_sorted, _ = torch.sort(x_sample.reshape(-1))
    x_sorted    = x_sorted.reshape(-1, 1)

    f_vals      = model.f2(model.f1(x_sorted) + model.res(x_sorted))
    first_diff  = f_vals[1:] - f_vals[:-1]
    second_diff = first_diff[1:] - first_diff[:-1]

    return torch.mean(second_diff ** 2)

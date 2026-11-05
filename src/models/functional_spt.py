"""
Functional SPT Model.

Residual network that maps cross-sectional rank → portfolio weight.
Inspired by Kom Samo & Vervuurt (2016) functional portfolio theory.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class FunctionalSPT(nn.Module):
    """
    Learned function f: rank_scalar → weight.

    Input  : (T, N)  — rank values per stock per day
    Output : (T, N)  — normalized portfolio weights

    Uses residual connection to stabilize training.
    Optional GARCH volatility penalty reduces allocation
    to high-vol stocks during inference.
    """

    def __init__(
        self,
        hidden_dim: int = 32,
        output_dim: int = 16,
        garch_penalty: float = 0.3,
    ):
        super().__init__()
        self.garch_penalty = garch_penalty

        # Main branch
        self.f1 = nn.Sequential(
            nn.Linear(1, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
        )

        # Output branch
        self.f2 = nn.Sequential(
            nn.Linear(hidden_dim, output_dim),
            nn.Tanh(),
            nn.Linear(output_dim, 1),
            nn.Softplus(),      # positive weights before normalization
        )

        # Residual projection
        self.res = nn.Linear(1, hidden_dim)

    def forward(
        self,
        x:     torch.Tensor,
        garch: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        T, N  = x.shape
        x_flat = x.reshape(-1, 1)

        out    = self.f1(x_flat) + self.res(x_flat)
        out    = self.f2(out)
        f_vals = out.reshape(T, N)

        weights = f_vals / f_vals.sum(dim=1, keepdim=True)

        if garch is not None:
            weights = weights / (1 + self.garch_penalty * garch)
            weights = weights / weights.sum(dim=1, keepdim=True)

        return weights

    # ----------------------------------------------------------
    # Checkpoint helpers
    # ----------------------------------------------------------

    def save(self, path: str, metadata: Optional[Dict] = None) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "state_dict":    self.state_dict(),
            "garch_penalty": self.garch_penalty,
            "metadata":      metadata or {},
        }
        torch.save(payload, path)
        logger.info("FunctionalSPT saved → %s", path)

    @classmethod
    def load(cls, path: str, **model_kwargs) -> "FunctionalSPT":
        payload        = torch.load(path, map_location="cpu", weights_only=False)
        meta           = payload.get("metadata", {})
        hidden_dim     = meta.get("hidden_dim",     model_kwargs.get("hidden_dim", 32))
        output_dim     = meta.get("output_dim",     model_kwargs.get("output_dim", 16))
        garch_penalty  = payload.get("garch_penalty", model_kwargs.get("garch_penalty", 0.3))

        model = cls(hidden_dim=hidden_dim, output_dim=output_dim, garch_penalty=garch_penalty)
        model.load_state_dict(payload["state_dict"])
        model.eval()
        logger.info("FunctionalSPT loaded ← %s | metadata: %s", path, meta)
        return model

"""Pydantic models for versioned incentive sets."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class Incentive(BaseModel):
    """A single incentive program with cost and redemption data."""

    name: str
    estimated_annual_cost_per_user: float
    redemption_rate: float
    # Cold-start certainty modeling:
    # - prior_strength controls how strongly redemption_rate is treated as prior belief.
    # - observed_* can be updated from pilots as real data arrives.
    uptake_prior_strength: float = 20.0
    uptake_observed_successes: int = 0
    uptake_observed_trials: int = 0


class IncentiveSet(BaseModel):
    """An immutable versioned set of incentive programs."""

    version: str  # e.g. "is_a3b2c1d4e5f6"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    name: str = ""
    description: str = ""
    is_default: bool = False
    incentive_count: int = 0
    incentives: list[Incentive] = []

"""Tests for statistical convergence in optimization iterations."""

import os
import sys
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.profile_catalog import CanonicalProfile
from profile_generator.optimization import (
    OptimizationState,
    ProfileIncentiveEvaluation,
    _is_statistically_converged,
    _process_profile,
)


def _make_profile(pid: str = "P0", ltv: float = 500.0, pop: int = 10) -> CanonicalProfile:
    return CanonicalProfile(
        profile_id=pid,
        label="Test Profile",
        centroid={"recency_days": 5.0, "transaction_count": 50.0},
        population_share=0.5,
        population_count=pop,
        description="A test profile",
        ltv=ltv,
        portfolio_ltv=ltv * pop,
    )


def _make_eval(profile_id: str, net_ltv: float, cost: float = 0.0) -> ProfileIncentiveEvaluation:
    return ProfileIncentiveEvaluation(
        profile_id=profile_id,
        selected_incentives=["2% flat cash back"],
        gross_ltv=net_ltv + cost,
        estimated_cost=cost,
        net_ltv=net_ltv,
        reasoning="test",
    )


def _make_state(max_iterations: int = 20, patience: int = 3, window: int = 6) -> OptimizationState:
    return OptimizationState(
        optimization_id="eid-test",
        catalog_version="v-test",
        status="running",
        progress=0,
        current_step="init",
        iterations_per_profile=0,
        available_incentives=[],
        started_at=datetime.utcnow(),
        max_iterations=max_iterations,
        patience=patience,
        convergence_window=window,
    )


def test_statistical_convergence_true_on_stable_series():
    values = [1000.0, 1001.0, 999.0, 1000.5, 999.5, 1000.0]
    assert _is_statistically_converged(values)


def test_statistical_convergence_false_on_trend():
    values = [1000.0, 1020.0, 1040.0, 1060.0, 1080.0, 1100.0]
    assert not _is_statistically_converged(values)


def test_process_profile_keeps_best_and_stops_before_max():
    profile = _make_profile(pop=1)
    state = _make_state(max_iterations=30, patience=3, window=6)

    # Improve early, then plateau with tiny noise around the same level.
    sequence = [510.0, 530.0, 548.0, 551.0, 550.8, 551.1, 550.9, 551.0, 551.0, 551.0]
    call_count = {"n": 0}

    def side_effect(*_args, **_kwargs):
        idx = min(call_count["n"], len(sequence) - 1)
        call_count["n"] += 1
        return _make_eval(profile.profile_id, sequence[idx], cost=5.0)

    with patch("profile_generator.optimization.evaluate_incentive_bundle", side_effect=side_effect):
        # Advance until profile finalizes.
        for _ in range(40):
            done = _process_profile(state, profile, cost_map={}, total_profiles=1)
            if done:
                break

    assert len(state.results) == 1
    assert state.results[0].new_net_portfolio_ltv == 551.1
    assert state.iterations_per_profile < state.max_iterations


def test_none_incentives_keeps_baseline_columns_consistent():
    profile = _make_profile(pop=10, ltv=500.0)
    state = _make_state(max_iterations=10, patience=2, window=4)

    # Always return baseline/no incentive result.
    def side_effect(*_args, **_kwargs):
        return ProfileIncentiveEvaluation(
            profile_id=profile.profile_id,
            selected_incentives=[],
            gross_ltv=profile.ltv,
            estimated_cost=0.0,
            net_ltv=profile.ltv,
            reasoning="none",
        )

    with patch("profile_generator.optimization.evaluate_incentive_bundle", side_effect=side_effect):
        for _ in range(20):
            done = _process_profile(state, profile, cost_map={}, total_profiles=1)
            if done:
                break

    assert len(state.results) == 1
    result = state.results[0]
    assert result.selected_incentives == ["None"]
    assert result.new_gross_portfolio_ltv == result.original_portfolio_ltv
    assert result.new_net_portfolio_ltv == result.original_portfolio_ltv
    assert result.portfolio_cost == 0.0
    assert result.lift == 0.0


def test_process_profile_updates_progress_within_active_profile():
    profile = _make_profile(pop=1)
    state = _make_state(max_iterations=50, patience=3, window=6)
    state.next_profile_index = 9
    state.progress = 90

    # Keep net flat so the profile does not finalize on the first call.
    def side_effect(*_args, **_kwargs):
        return _make_eval(profile.profile_id, 505.0, cost=1.0)

    with patch("profile_generator.optimization.evaluate_incentive_bundle", side_effect=side_effect):
        done = _process_profile(state, profile, cost_map={}, total_profiles=10)

    assert done is False
    # Progress should move off the whole-profile boundary while iterating.
    assert state.progress > 90

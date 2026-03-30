"""Tests for the Monte Carlo optimization engine."""

import math
import numpy as np
import pytest

from models.monte_carlo import (
    MonteCarloProfileResult,
    MonteCarloBundleComparison,
    MonteCarloOptimizationResult,
    SensitivityEntry,
)
from models.incentive_set import Incentive
from models.profile_catalog import CanonicalProfile
from profile_generator.monte_carlo import (
    _beta_params,
    _marginal_ltv_estimate,
    _simulate_bundle,
    _generate_candidate_bundles,
)


# --- Model tests ---

class TestMonteCarloModels:
    def test_profile_result_creation(self):
        result = MonteCarloProfileResult(
            profile_id="P0",
            bundle_name="Test",
            selected_incentives=["Cash back"],
            n_simulations=100,
            uptake_params={"Cash back": {"alpha": 2.0, "beta": 8.0}},
            net_ltv_percentiles={"p5": 90, "p25": 95, "p50": 100, "p75": 105, "p95": 110},
            expected_net_ltv=100.0,
            expected_gross_ltv=120.0,
            expected_cost=20.0,
            expected_lift=10.0,
            confidence_interval_90=(90.0, 110.0),
            probability_positive_lift=0.85,
        )
        assert result.profile_id == "P0"
        assert result.probability_positive_lift == 0.85
        assert result.confidence_interval_90 == (90.0, 110.0)

    def test_sensitivity_entry(self):
        entry = SensitivityEntry(
            param_name="Uptake rate",
            base_value=1000.0,
            low_delta=-200.0,
            high_delta=150.0,
        )
        assert entry.param_name == "Uptake rate"
        assert entry.low_delta == -200.0

    def test_optimization_result_to_legacy(self):
        profile_result = MonteCarloProfileResult(
            profile_id="P0",
            bundle_name="Full",
            selected_incentives=["A", "B"],
            n_simulations=100,
            uptake_params={},
            net_ltv_percentiles={"p5": 90, "p25": 95, "p50": 100, "p75": 105, "p95": 110},
            expected_net_ltv=100.0,
            expected_gross_ltv=130.0,
            expected_cost=30.0,
            expected_lift=10.0,
            confidence_interval_90=(90.0, 110.0),
            probability_positive_lift=0.9,
        )
        opt_result = MonteCarloOptimizationResult(
            optimization_id="mc_test",
            catalog_version="v1",
            incentive_set_version="is1",
            status="completed",
            n_simulations=100,
            profiles=[MonteCarloBundleComparison(
                profile_id="P0",
                best_bundle=profile_result,
                alternatives=[],
            )],
            started_at="2026-01-01T00:00:00",
            total_original_ltv=90.0,
            total_new_net_ltv=100.0,
            total_lift=10.0,
            total_cost=30.0,
        )
        legacy = opt_result.to_legacy_results()
        assert len(legacy) == 1
        assert legacy[0]["profile_id"] == "P0"
        assert legacy[0]["new_net_portfolio_ltv"] == 100.0
        assert "percentiles" in legacy[0]
        assert "probability_positive_lift" in legacy[0]
        assert legacy[0]["probability_positive_lift"] == 0.9


# --- Engine function tests ---

class TestBetaParams:
    def test_default_params(self):
        inc = Incentive(name="Test", estimated_annual_cost_per_user=100, redemption_rate=0.3)
        alpha, beta = _beta_params(inc)
        assert alpha > 0
        assert beta > 0
        # With default prior_strength=20, redemption_rate=0.3:
        # alpha = 0.3 * 20 = 6, beta = 0.7 * 20 = 14
        assert abs(alpha - 6.0) < 0.1
        assert abs(beta - 14.0) < 0.1

    def test_with_observed_data(self):
        inc = Incentive(
            name="Test",
            estimated_annual_cost_per_user=100,
            redemption_rate=0.3,
            uptake_observed_successes=10,
            uptake_observed_trials=50,
        )
        alpha, beta = _beta_params(inc)
        # alpha = 0.3*20 + 10 = 16, beta = 0.7*20 + 40 = 54
        assert abs(alpha - 16.0) < 0.1
        assert abs(beta - 54.0) < 0.1

    def test_zero_redemption_rate(self):
        inc = Incentive(name="Test", estimated_annual_cost_per_user=100, redemption_rate=0.0)
        alpha, beta = _beta_params(inc)
        assert alpha >= 0.01  # clamped
        assert beta > 0

    def test_full_redemption_rate(self):
        inc = Incentive(name="Test", estimated_annual_cost_per_user=100, redemption_rate=1.0)
        alpha, beta = _beta_params(inc)
        assert alpha > 0
        assert beta >= 0.01  # clamped


class TestMarginalLtvEstimate:
    def test_high_ltv_profile(self):
        profile = CanonicalProfile(profile_id="P0", ltv=1000, population_count=100)
        inc = Incentive(name="Test", estimated_annual_cost_per_user=50, redemption_rate=0.3)
        marginal = _marginal_ltv_estimate(profile, inc)
        # ltv_ratio = 1000/50 = 20, capped at 10. mult = 1 + log1p(10) ~= 3.4
        assert marginal > 50  # Should be more than the cost
        assert marginal < 500  # But not absurdly high

    def test_low_ltv_profile(self):
        profile = CanonicalProfile(profile_id="P0", ltv=10, population_count=100)
        inc = Incentive(name="Test", estimated_annual_cost_per_user=100, redemption_rate=0.3)
        marginal = _marginal_ltv_estimate(profile, inc)
        # ltv_ratio = 10/100 = 0.1, mult = 1 + log1p(0.1) ~= 1.095
        assert marginal < 150  # Close to break-even

    def test_zero_ltv_uses_minimum(self):
        profile = CanonicalProfile(profile_id="P0", ltv=0, population_count=100)
        inc = Incentive(name="Test", estimated_annual_cost_per_user=50, redemption_rate=0.3)
        marginal = _marginal_ltv_estimate(profile, inc)
        assert marginal > 0


class TestSimulateBundle:
    def test_empty_bundle_returns_baseline(self):
        profile = CanonicalProfile(profile_id="P0", ltv=100, population_count=10, portfolio_ltv=1000)
        rng = np.random.default_rng(42)
        result = _simulate_bundle(profile, [], "No incentives", 1000, rng)
        assert result.expected_net_ltv == 1000.0
        assert result.expected_lift == 0.0
        assert result.expected_cost == 0.0
        assert result.probability_positive_lift == 0.0

    def test_single_incentive_bundle(self):
        profile = CanonicalProfile(profile_id="P0", ltv=100, population_count=10, portfolio_ltv=1000)
        inc = Incentive(name="Cash back", estimated_annual_cost_per_user=50, redemption_rate=0.3)
        rng = np.random.default_rng(42)
        result = _simulate_bundle(profile, [inc], "Cash back", 5000, rng)

        assert result.profile_id == "P0"
        assert result.bundle_name == "Cash back"
        assert result.n_simulations == 5000
        assert "p5" in result.net_ltv_percentiles
        assert "p50" in result.net_ltv_percentiles
        assert "p95" in result.net_ltv_percentiles
        assert result.net_ltv_percentiles["p5"] <= result.net_ltv_percentiles["p50"]
        assert result.net_ltv_percentiles["p50"] <= result.net_ltv_percentiles["p95"]
        assert 0 <= result.probability_positive_lift <= 1

    def test_multiple_incentives(self):
        profile = CanonicalProfile(profile_id="P0", ltv=200, population_count=10, portfolio_ltv=2000)
        incs = [
            Incentive(name="A", estimated_annual_cost_per_user=30, redemption_rate=0.4),
            Incentive(name="B", estimated_annual_cost_per_user=50, redemption_rate=0.2),
        ]
        rng = np.random.default_rng(42)
        result = _simulate_bundle(profile, incs, "AB", 1000, rng)
        assert len(result.selected_incentives) == 2
        assert len(result.uptake_params) == 2

    def test_reproducibility(self):
        profile = CanonicalProfile(profile_id="P0", ltv=100, population_count=10, portfolio_ltv=1000)
        inc = Incentive(name="X", estimated_annual_cost_per_user=40, redemption_rate=0.25)

        r1 = _simulate_bundle(profile, [inc], "X", 1000, np.random.default_rng(42))
        r2 = _simulate_bundle(profile, [inc], "X", 1000, np.random.default_rng(42))
        assert r1.expected_net_ltv == r2.expected_net_ltv


class TestGenerateCandidateBundles:
    def test_generates_baseline_plus_singletons(self):
        incs = [
            Incentive(name="A", estimated_annual_cost_per_user=10, redemption_rate=0.3),
            Incentive(name="B", estimated_annual_cost_per_user=20, redemption_rate=0.5),
        ]
        bundles = _generate_candidate_bundles(incs)
        names = [b[0] for b in bundles]
        assert "No incentives" in names
        assert "A" in names
        assert "B" in names
        assert "Full bundle" in names
        assert len(bundles) == 4  # no_inc + 2 singles + full

    def test_single_incentive_no_full_bundle(self):
        incs = [Incentive(name="A", estimated_annual_cost_per_user=10, redemption_rate=0.3)]
        bundles = _generate_candidate_bundles(incs)
        names = [b[0] for b in bundles]
        assert "Full bundle" not in names
        assert len(bundles) == 2  # no_inc + singleton

    def test_empty_incentives(self):
        bundles = _generate_candidate_bundles([])
        assert len(bundles) == 1  # just "No incentives"
        assert bundles[0][0] == "No incentives"

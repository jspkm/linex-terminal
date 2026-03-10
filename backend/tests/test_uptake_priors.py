"""Tests for cold-start Bayesian uptake priors."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from profile_generator.incentive_manager import get_incentive_cost_map


def test_cost_map_defaults_to_redemption_rate_without_history():
    incentives = [
        {
            "name": "A",
            "estimated_annual_cost_per_user": 100.0,
            "redemption_rate": 0.6,
        }
    ]
    costs = get_incentive_cost_map(incentives)
    assert costs["A"] == 60.0


def test_cost_map_updates_with_observed_uptake():
    incentives = [
        {
            "name": "B",
            "estimated_annual_cost_per_user": 100.0,
            "redemption_rate": 0.5,
            "uptake_prior_strength": 20.0,
            "uptake_observed_successes": 80,
            "uptake_observed_trials": 100,
        }
    ]
    costs = get_incentive_cost_map(incentives)
    # Posterior mean should move above 0.5 after strong positive evidence.
    assert costs["B"] > 50.0


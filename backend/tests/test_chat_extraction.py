"""Tests for budget and target LTV extraction from user messages."""

import pytest
from handlers.chat import _extract_budget, _extract_target_ltv, _parse_dollar_amount


class TestParseDollarAmount:
    def test_million_shorthand(self):
        assert _parse_dollar_amount("$1M") == 1_000_000
        assert _parse_dollar_amount("$2.5m") == 2_500_000
        assert _parse_dollar_amount("$1 million") == 1_000_000

    def test_thousand_shorthand(self):
        assert _parse_dollar_amount("$500k") == 500_000
        assert _parse_dollar_amount("$250K") == 250_000

    def test_billion_shorthand(self):
        assert _parse_dollar_amount("$1b") == 1_000_000_000
        assert _parse_dollar_amount("$1 billion") == 1_000_000_000

    def test_raw_number(self):
        assert _parse_dollar_amount("$1000000") == 1_000_000
        assert _parse_dollar_amount("$50000") == 50_000

    def test_small_amount_ignored(self):
        assert _parse_dollar_amount("$50") is None  # below 1000 threshold

    def test_no_dollar_sign(self):
        assert _parse_dollar_amount("optimize") is None

    def test_with_spaces(self):
        assert _parse_dollar_amount("$ 1M") == 1_000_000


class TestExtractBudget:
    def test_budget_keyword(self):
        assert _extract_budget("optimize with $1M budget") == 1_000_000

    def test_spend_keyword(self):
        assert _extract_budget("spend no more than $500k") == 500_000

    def test_cap_keyword(self):
        assert _extract_budget("cap at $2M") == 2_000_000

    def test_spending_cap(self):
        assert _extract_budget("set spending cap to $750k") == 750_000

    def test_no_budget_keyword(self):
        # Dollar amount without budget keyword should NOT trigger
        assert _extract_budget("optimize with target ltv of $5M") is None

    def test_no_dollar_amount(self):
        assert _extract_budget("set a budget") is None

    def test_general_message(self):
        assert _extract_budget("optimize my portfolio") is None

    def test_case_insensitive(self):
        assert _extract_budget("BUDGET of $1M") == 1_000_000


class TestExtractTargetLtv:
    def test_target_ltv(self):
        assert _extract_target_ltv("target ltv of $5M") == 5_000_000

    def test_target_final(self):
        assert _extract_target_ltv("target final ltv of $8M") == 8_000_000

    def test_net_ltv(self):
        assert _extract_target_ltv("net ltv of $3M") == 3_000_000

    def test_target_value(self):
        assert _extract_target_ltv("target value $10M") == 10_000_000

    def test_target_of(self):
        assert _extract_target_ltv("target of $2.5M") == 2_500_000

    def test_no_target_keyword(self):
        # Budget keyword should NOT trigger target extraction
        assert _extract_target_ltv("optimize with $1M budget") is None

    def test_no_dollar_amount(self):
        assert _extract_target_ltv("target ltv") is None

    def test_general_message(self):
        assert _extract_target_ltv("optimize my portfolio") is None

    def test_case_insensitive(self):
        assert _extract_target_ltv("TARGET LTV $5M") == 5_000_000


class TestBudgetTargetSeparation:
    """Ensure budget and target LTV don't cross-trigger."""

    def test_budget_does_not_trigger_target(self):
        msg = "optimize with $1M budget"
        assert _extract_budget(msg) == 1_000_000
        assert _extract_target_ltv(msg) is None

    def test_target_does_not_trigger_budget(self):
        msg = "target ltv of $5M"
        assert _extract_target_ltv(msg) == 5_000_000
        assert _extract_budget(msg) is None

    def test_both_in_one_message(self):
        msg = "optimize with $1M budget and target ltv of $5M"
        budget = _extract_budget(msg)
        target = _extract_target_ltv(msg)
        # Both should find a dollar amount (parser finds first match in each case)
        assert budget is not None
        assert target is not None

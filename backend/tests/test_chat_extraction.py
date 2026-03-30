"""Tests for budget, target LTV, and what-if extraction from user messages."""

import pytest
from handlers.chat import _extract_budget, _extract_target_ltv, _extract_what_if, _parse_dollar_amount


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


class TestExtractWhatIf:
    """Tests for what-if uptake/cost override extraction."""

    # --- uptake extraction ---
    def test_what_if_uptake(self):
        uptake, cost = _extract_what_if("what if uptake is 20%?")
        assert uptake == pytest.approx(0.2)
        assert cost is None

    def test_what_if_uptake_drops_to(self):
        uptake, cost = _extract_what_if("what if uptake drops to 10%?")
        assert uptake == pytest.approx(0.1)
        assert cost is None

    def test_what_if_uptake_increases_to(self):
        uptake, cost = _extract_what_if("what happens if uptake increases to 50%?")
        assert uptake == pytest.approx(0.5)
        assert cost is None

    def test_suppose_uptake(self):
        uptake, cost = _extract_what_if("suppose uptake is 35%")
        assert uptake == pytest.approx(0.35)
        assert cost is None

    def test_assume_does_not_trigger(self):
        uptake, cost = _extract_what_if("assuming uptake at 15%")
        assert uptake is None
        assert cost is None

    def test_uptake_clamped_to_1(self):
        uptake, _ = _extract_what_if("what if uptake is 150%?")
        assert uptake == 1.0

    def test_uptake_clamped_to_0(self):
        uptake, _ = _extract_what_if("what if uptake is 0%?")
        assert uptake == 0.0

    # --- cost extraction ---
    def test_what_if_cost(self):
        uptake, cost = _extract_what_if("what if cost is $50?")
        assert uptake is None
        assert cost == 50.0

    def test_what_if_cost_drops_to(self):
        uptake, cost = _extract_what_if("what if cost drops to $30?")
        assert uptake is None
        assert cost == 30.0

    def test_suppose_cost(self):
        uptake, cost = _extract_what_if("suppose cost is $100")
        assert uptake is None
        assert cost == 100.0

    # --- both ---
    def test_both_uptake_and_cost(self):
        uptake, cost = _extract_what_if("what if uptake is 20% and cost is $50?")
        assert uptake == pytest.approx(0.2)
        assert cost == 50.0

    # --- no match ---
    def test_no_what_if_keyword(self):
        uptake, cost = _extract_what_if("optimize with uptake at 20%")
        assert uptake is None
        assert cost is None

    def test_what_if_no_values(self):
        uptake, cost = _extract_what_if("what if things change?")
        assert uptake is None
        assert cost is None

    def test_general_message(self):
        uptake, cost = _extract_what_if("show me the results")
        assert uptake is None
        assert cost is None

    def test_case_insensitive(self):
        uptake, cost = _extract_what_if("WHAT IF UPTAKE IS 25%?")
        assert uptake == pytest.approx(0.25)
        assert cost is None

    def test_scenario_where_keyword(self):
        uptake, cost = _extract_what_if("scenario where uptake is 40%")
        assert uptake == pytest.approx(0.4)
        assert cost is None

    def test_hypothetical_keyword(self):
        uptake, cost = _extract_what_if("hypothetical: uptake to 30% and cost to $75")
        assert uptake == pytest.approx(0.3)
        assert cost == 75.0

    def test_decimal_uptake(self):
        uptake, _ = _extract_what_if("what if uptake is 12.5%?")
        assert uptake == pytest.approx(0.125)

    def test_decimal_cost(self):
        _, cost = _extract_what_if("what if cost is $49.99?")
        assert cost == pytest.approx(49.99)

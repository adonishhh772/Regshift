import pytest

from app.services.simulator import (
    OBLIGATION_APPROVAL_LOGGED,
    OBLIGATION_FINANCE_APPROVAL,
    OBLIGATION_SUPPLIER_BLOCKED,
    run_simulation,
)


PROCUREMENT_CONTRACT = {
    "domain": "procurement",
    "entity": "purchase_order",
    "trigger": {"condition": "total_amount > 25000"},
    "required_behaviour": [
        OBLIGATION_FINANCE_APPROVAL,
        OBLIGATION_SUPPLIER_BLOCKED,
        OBLIGATION_APPROVAL_LOGGED,
    ],
    "exceptions": ["purchase_orders_under_or_equal_to_25000_follow_existing_flow"],
    "approval_roles": ["Finance Manager", "Procurement Owner"],
    "required_tests": [
        "purchase order above £25,000 without approval is blocked",
        "purchase order under £25,000 follows existing flow",
    ],
}


def test_simulation_is_contract_driven():
    result = run_simulation(PROCUREMENT_CONTRACT, "procurement")

    assert result["contract_driven"] is True
    assert len(result["before"]) == len(result["after"])
    assert len(result["scenario_rules"]) == len(result["before"])
    assert "25000" in result["summary"] or "25,000" in result["summary"]


def test_simulation_uses_contract_threshold_amounts():
    result = run_simulation(PROCUREMENT_CONTRACT, "procurement")

    under_case = result["before"][0]
    over_case = result["before"][1]

    assert under_case.amount == 20000
    assert over_case.amount == 30000
    assert under_case.verdict == "pass"
    assert over_case.verdict == "policy violation"
    assert result["after"][1].result == "blocked"


def test_simulation_adds_obligation_specific_cases():
    result = run_simulation(PROCUREMENT_CONTRACT, "procurement")
    labels = [case.label for case in result["before"]]

    assert any("Supplier confirmation" in label for label in labels)
    assert any("Approval event audit" in label for label in labels)
    assert any("Unauthorized role" in label for label in labels)


def test_simulation_respects_custom_threshold():
    contract = {
        **PROCUREMENT_CONTRACT,
        "trigger": {"condition": "total_amount > 50000"},
    }
    result = run_simulation(contract, "procurement")

    assert result["before"][1].amount == 60000
    assert "50,000" in result["summary"]


def test_simulation_hr_domain_uses_hours():
    contract = {
        "entity": "employee",
        "trigger": {"condition": "weekly_hours > 48"},
        "required_behaviour": ["manager_review_required"],
        "exceptions": ["under_48_hours_allowed"],
        "approval_roles": ["Manager"],
    }
    result = run_simulation(contract, "hr_compliance")

    assert result["before"][0].amount == 40
    assert result["before"][1].amount == 60
    assert "hour" in result["summary"].lower()

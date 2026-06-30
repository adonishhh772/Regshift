import pytest

from app.database import get_connection, init_db
from app.services.policy_compiler import (
    build_governance_config,
    evaluate_contract_policy_compliance,
    merge_policy_into_contract,
)
from app.services.policy_ingestor import ingest_policy_document
from app.services.policy_graph import persist_policy_knowledge_graph
from app.services.policy_seed import seed_demo_policies
from app.services.policy_store import activate_policy, get_active_policy, ingest_policy, list_policies


DEMO_POLICY = """
ACME Corp Procurement Policy v2.1

Section 4.2 - Purchase Order Approval
All purchase orders with a total amount exceeding £25,000 must receive
Finance Manager approval before supplier confirmation is permitted.

Section 4.3 - Supplier Confirmation Controls
Supplier confirmation must be blocked until required approval is obtained.

Section 5.1 - Audit Requirements
Every approval event must be logged with approver identity and timestamp.

Section 6.1 - Agent Automation Limits
No autonomous system changes to procurement approval workflows are permitted.
All changes require human approval before merge to production.

Section 7.1 - Required Sign-off Roles
- Finance Manager
- Procurement Owner
- Compliance Reviewer
"""


@pytest.fixture(autouse=True)
def setup_policy_db():
    init_db()
    connection = get_connection()
    connection.execute("DELETE FROM tenant_policies")
    connection.commit()
    connection.close()
    yield


@pytest.fixture
def seeded_policy():
    parsed = ingest_policy_document(
        title="Test Procurement Policy",
        source_text=DEMO_POLICY,
        domain="procurement",
    )
    stored = ingest_policy(
        title=parsed["title"],
        source_text=DEMO_POLICY,
        rules=parsed,
        domain="procurement",
    )
    persist_policy_knowledge_graph(stored["tenant_id"], stored)
    return stored


def test_ingest_policy_document_extracts_rules():
    parsed = ingest_policy_document(
        title="Test Policy",
        source_text=DEMO_POLICY,
        domain="procurement",
    )
    assert parsed["domain"] == "procurement"
    assert parsed["threshold"] == 25000
    assert "finance_approval_required" in parsed["obligations"]
    assert "supplier_confirmation_blocked_until_approval" in parsed["obligations"]
    assert "approval_event_logged" in parsed["obligations"]
    assert "Finance Manager" in parsed["approval_roles"]
    assert parsed["agent_limits"]["can_auto_merge"] is False
    assert parsed["rule_count"] >= 5


def test_build_governance_config_from_active_policy(seeded_policy):
    config = build_governance_config("procurement")
    assert config is not None
    assert config["policy_id"] == seeded_policy["id"]
    assert config["threshold"] == 25000
    assert "finance_approval_required" in config["obligations"]


def test_merge_policy_into_contract_adds_citations(seeded_policy):
    base_contract = {
        "domain": "procurement",
        "entity": "purchase_order",
        "required_behaviour": ["finance_approval_required"],
        "approval_roles": ["Engineering Reviewer"],
        "risks": {},
    }
    merged = merge_policy_into_contract(base_contract, "procurement")
    assert merged["policy_source"]["policy_id"] == seeded_policy["id"]
    assert merged["policy_threshold"] == 25000
    assert "Finance Manager" in merged["approval_roles"]
    assert merged["agent_limits"]["can_auto_merge"] is False
    assert "finance_approval_required" in merged["policy_citations"]


def test_evaluate_contract_policy_compliance_passes(seeded_policy):
    contract = merge_policy_into_contract(
        {
            "domain": "procurement",
            "entity": "purchase_order",
            "required_behaviour": [
                "finance_approval_required",
                "supplier_confirmation_blocked_until_approval",
                "approval_event_logged",
            ],
            "approval_roles": ["Finance Manager", "Procurement Owner", "Compliance Reviewer"],
            "agent_limits": {"can_auto_merge": False},
            "trigger": {"condition": "total_amount > 25000"},
            "policy_threshold": 25000,
            "policy_citations": {"finance_approval_required": "Section 4.2"},
        },
        "procurement",
    )
    checks = evaluate_contract_policy_compliance(contract, "procurement")
    assert all(check["passed"] for check in checks)


def test_evaluate_contract_policy_compliance_fails_missing_obligations(seeded_policy):
    contract = {
        "domain": "procurement",
        "required_behaviour": [],
        "approval_roles": [],
        "agent_limits": {"can_auto_merge": True},
    }
    checks = evaluate_contract_policy_compliance(contract, "procurement")
    failed_ids = {check["id"] for check in checks if not check["passed"]}
    assert "contract_obligations_policy_compliant" in failed_ids
    assert "agent_limits_policy_derived" in failed_ids


def test_seed_demo_policies_idempotent():
    first = seed_demo_policies()
    second = seed_demo_policies()
    assert first is not None or get_active_policy("procurement") is not None
    assert second is None
    policies = list_policies()
    active_domains = {policy["domain"] for policy in policies if policy["status"] == "active"}
    assert "procurement" in active_domains
    assert "inventory" in active_domains
    assert "finance_billing" in active_domains


def test_ingest_policy_archives_previous_version(seeded_policy):
    parsed = ingest_policy_document(
        title="Test Procurement Policy v2",
        source_text=DEMO_POLICY,
        domain="procurement",
    )
    second = ingest_policy(
        title="Test Procurement Policy v2",
        source_text=DEMO_POLICY,
        rules=parsed,
        domain="procurement",
    )
    policies = list_policies()
    procurement_policies = [policy for policy in policies if policy["domain"] == "procurement"]
    assert len(procurement_policies) == 2
    archived = [policy for policy in procurement_policies if policy["status"] == "archived"]
    active = [policy for policy in procurement_policies if policy["status"] == "active"]
    assert len(archived) == 1
    assert len(active) == 1
    assert active[0]["id"] == second["id"]
    assert archived[0]["id"] == seeded_policy["id"]


def test_activate_policy_restores_archived_version(seeded_policy):
    parsed = ingest_policy_document(
        title="Test Procurement Policy v2",
        source_text=DEMO_POLICY,
        domain="procurement",
    )
    second = ingest_policy(
        title="Test Procurement Policy v2",
        source_text=DEMO_POLICY,
        rules=parsed,
        domain="procurement",
    )
    restored = activate_policy(seeded_policy["id"])
    assert restored is not None
    assert restored["status"] == "active"
    assert get_active_policy("procurement")["id"] == seeded_policy["id"]
    second_row = next(policy for policy in list_policies() if policy["id"] == second["id"])
    assert second_row["status"] == "archived"

import pytest

from app.database import get_connection, init_db
from app.services.policy_graph import (
    extract_workflow_guidance,
    get_policy_graph_visualization,
    persist_policy_knowledge_graph,
)
from app.services.policy_ingestor import ingest_policy_document
from app.services.policy_store import ingest_policy
from app.services.langfuse_tracer import langfuse_status


DEMO_POLICY = """
ACME Corp Procurement Policy v2.1
Section 4.2 - Purchase orders exceeding £25,000 require Finance Manager approval.
Section 4.3 - Supplier confirmation must be blocked until approval is obtained.
Section 5.1 - Every approval event must be logged.
Section 6.1 - No autonomous changes. Human approval required before merge.
Section 7.1 - Required Sign-off Roles
- Finance Manager
- Procurement Owner
"""


@pytest.fixture(autouse=True)
def setup_graph_db():
    init_db()
    connection = get_connection()
    connection.execute("DELETE FROM tenant_policies")
    connection.commit()
    connection.close()
    yield


@pytest.fixture
def seeded_policy_graph():
    parsed = ingest_policy_document(
        title="Graph Policy",
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


def test_extract_workflow_guidance_configured(seeded_policy_graph):
    guidance = extract_workflow_guidance("procurement")
    assert guidance["configured"] is True
    assert guidance["policy_id"] == seeded_policy_graph["id"]
    assert "finance_approval_required" in guidance["required_obligations"]
    assert "policy_graph_load" in guidance["required_steps"]


def test_extract_workflow_guidance_missing_policy():
    guidance = extract_workflow_guidance("inventory")
    assert guidance["configured"] is False
    assert "Ingest tenant policy" in guidance["message"]


def test_policy_graph_visualization(seeded_policy_graph):
    graph = get_policy_graph_visualization("procurement")
    assert len(graph["nodes"]) >= 1
    assert graph["backend"] in {"neo4j", "networkx_fallback"}
    assert graph["policy_id"] == seeded_policy_graph["id"]


def test_policy_graph_visualization_by_policy_id(seeded_policy_graph):
    graph = get_policy_graph_visualization(
        "procurement",
        policy_id=seeded_policy_graph["id"],
    )
    assert graph["policy_id"] == seeded_policy_graph["id"]
    assert graph["policy_title"] == seeded_policy_graph["title"]
    assert len(graph["nodes"]) >= 1


def test_merge_policy_into_contract_with_neo4j_governance(seeded_policy_graph):
    from app.services.policy_compiler import merge_policy_into_contract

    merged = merge_policy_into_contract(
        {
            "domain": "procurement",
            "entity": "purchase_order",
            "required_behaviour": ["finance_approval_required"],
            "approval_roles": [],
            "risks": {},
        },
        "procurement",
    )
    assert merged["policy_source"]["policy_id"] == seeded_policy_graph["id"]
    assert "finance_approval_required" in merged["policy_citations"]


def test_langfuse_status_disabled_by_default():
    status = langfuse_status()
    assert status["enabled"] is False


def test_trace_regshift_step_noop_when_disabled():
    from app.services.langfuse_tracer import trace_regshift_step

    with trace_regshift_step("test-step", "session-1", domain="procurement") as context:
        assert context is not None
        context["data"] = {"ok": True}

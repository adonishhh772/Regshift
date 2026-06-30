import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import init_db, get_connection
from app.services.policy_seed import seed_demo_policies

GOLDEN_TEXT = (
    "From next quarter, all purchase orders above £25,000 must require finance approval "
    "before supplier confirmation. The system must log who approved it and block "
    "confirmation if approval is missing."
)

DEMO_POLICY = """
ACME Corp Procurement Policy v2.1
Section 4.2 - Purchase Order Approval
All purchase orders with a total amount exceeding £25,000 must receive
Finance Manager approval before supplier confirmation is permitted.
Section 4.3 - Supplier confirmation must be blocked until required approval is obtained.
Section 5.1 - Every approval event must be logged with approver identity and timestamp.
Section 6.1 - No autonomous system changes are permitted. All changes require human approval.
Section 7.1 - Required Sign-off Roles
- Finance Manager
- Procurement Owner
- Compliance Reviewer
"""


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    connection = get_connection()
    connection.execute("DELETE FROM change_sessions")
    connection.execute("DELETE FROM file_index")
    connection.execute("DELETE FROM index_meta")
    connection.execute("DELETE FROM tenant_policies")
    connection.commit()
    connection.close()
    seed_demo_policies()
    yield

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_live(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_procurement_golden_path(client):
    classify = await client.post("/api/change/classify", json={"text": GOLDEN_TEXT})
    assert classify.status_code == 200
    session_id = classify.json()["session_id"]
    assert classify.json()["domain"] == "procurement"

    contract = await client.post(
        "/api/contract/generate",
        json={"text": GOLDEN_TEXT, "session_id": session_id},
    )
    assert contract.status_code == 200
    assert "finance_approval_required" in contract.json()["contract_yaml"]
    assert contract.json()["confidence"] == "policy_sourced"
    assert "policy_source" in contract.json()["contract"]

    approve = await client.post(
        "/api/contract/approve",
        json={"session_id": session_id, "contract_yaml": contract.json()["contract_yaml"]},
    )
    assert approve.status_code == 200
    assert approve.json()["approved"] is True

    await client.post("/api/index/scan")
    impact = await client.post("/api/impact/analyze", json={"session_id": session_id})
    assert impact.status_code == 200
    assert len(impact.json()["files"]) > 0

    graph = await client.get(f"/api/graph/current?session_id={session_id}")
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) > 0

    risk = await client.post("/api/risk/score", json={"session_id": session_id})
    assert risk.status_code == 200
    assert risk.json()["risks"]["financial_control"] == "high"
    assert risk.json()["autonomous_change_allowed"] is False

    tests = await client.post(f"/api/tests/generate?session_id={session_id}")
    assert tests.status_code == 200
    assert len(tests.json()["tests"]) >= 5

    simulation = await client.post(f"/api/simulation/run?session_id={session_id}")
    assert simulation.status_code == 200
    before = simulation.json()["before"]
    after = simulation.json()["after"]
    assert before[1]["verdict"] == "policy violation"
    assert after[1]["result"] == "blocked"

    governance = await client.get(f"/api/governance/evaluate?session_id={session_id}")
    assert governance.status_code == 200
    assert governance.json()["passed"] is True
    check_ids = {check["id"] for check in governance.json()["checks"]}
    assert "tenant_policy_active" in check_ids
    assert "contract_obligations_policy_compliant" in check_ids

    pack = await client.post("/api/pack/generate", json={"session_id": session_id})
    assert pack.status_code == 200
    assert "Executive Summary" in pack.json()["markdown"]


@pytest.mark.asyncio
async def test_classifier_all_domains(client):
    scenarios = {
        "procurement": "purchase order above £25,000 finance approval supplier confirmation",
        "inventory": "stock transfer warehouse manager approval dispatch",
        "finance_billing": "invoice recurring charges cancellation fees refund terms customer",
        "hr_compliance": "employee 48 hours compliance warning manager review",
        "security": "role change financial permissions administrator review logged",
    }
    for domain, text in scenarios.items():
        response = await client.post("/api/change/classify", json={"text": text})
        assert response.status_code == 200
        assert response.json()["domain"] == domain


@pytest.mark.asyncio
async def test_policy_graph_and_workflow_guidance(client):
    graph = await client.get("/api/policy/graph/procurement")
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) >= 1

    guidance = await client.get("/api/policy/workflow-guidance/procurement")
    assert guidance.status_code == 200
    assert guidance.json()["configured"] is True


@pytest.mark.asyncio
async def test_workflow_trace_summary(client):
    classify = await client.post("/api/change/classify", json={"text": GOLDEN_TEXT})
    session_id = classify.json()["session_id"]
    trace = await client.get(f"/api/traces/workflow/{session_id}")
    assert trace.status_code == 200
    body = trace.json()
    assert body["session_id"] == session_id
    assert len(body["steps"]) >= 10
    assert "langfuse" in body


@pytest.mark.asyncio
async def test_health_includes_langfuse(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert "langfuse" in response.json()


@pytest.mark.asyncio
async def test_messy_input_still_compiles(client):
    messy = (
        "Starting Q2, procurement must ensure purchase orders exceeding twenty-five thousand pounds "
        "get finance sign-off prior to supplier confirmation, with full audit logging"
    )
    classify = await client.post("/api/change/classify", json={"text": messy})
    contract = await client.post(
        "/api/contract/generate",
        json={"text": messy, "session_id": classify.json()["session_id"]},
    )
    assert contract.status_code == 200
    assert "25000" in contract.json()["contract_yaml"]


@pytest.mark.asyncio
async def test_policy_ingest_and_governance_config(client):
    response = await client.post(
        "/api/policy/ingest",
        json={
            "title": "Test Procurement Policy",
            "source_text": DEMO_POLICY,
            "domain": "procurement",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rule_count"] >= 5
    assert body["policy"]["domain"] == "procurement"

    active = await client.get("/api/policy/active/procurement")
    assert active.status_code == 200
    assert active.json()["title"] == "Test Procurement Policy"

    config = await client.get("/api/policy/governance/procurement")
    assert config.status_code == 200
    assert config.json()["configured"] is True
    assert config.json()["threshold"] == 25000


@pytest.mark.asyncio
async def test_policy_list_and_activate(client):
    first = await client.post(
        "/api/policy/ingest",
        json={
            "title": "Procurement Policy v1",
            "source_text": DEMO_POLICY,
            "domain": "procurement",
        },
    )
    assert first.status_code == 200
    first_policy_id = first.json()["policy"]["id"]

    second = await client.post(
        "/api/policy/ingest",
        json={
            "title": "Procurement Policy v2",
            "source_text": DEMO_POLICY,
            "domain": "procurement",
        },
    )
    assert second.status_code == 200

    listing = await client.get("/api/policy/list")
    assert listing.status_code == 200
    body = listing.json()
    procurement_policies = [policy for policy in body["policies"] if policy["domain"] == "procurement"]
    assert len(procurement_policies) == 3
    assert "procurement" in body["active_domains"]

    detail = await client.get(f"/api/policy/{first_policy_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "archived"

    activated = await client.post(f"/api/policy/{first_policy_id}/activate")
    assert activated.status_code == 200
    assert activated.json()["policy"]["status"] == "active"
    assert activated.json()["node_count"] >= 0


@pytest.mark.asyncio
async def test_governance_blocked_without_policy(client):
    connection = get_connection()
    connection.execute("DELETE FROM tenant_policies")
    connection.commit()
    connection.close()

    classify = await client.post("/api/change/classify", json={"text": GOLDEN_TEXT})
    session_id = classify.json()["session_id"]
    contract = await client.post(
        "/api/contract/generate",
        json={"text": GOLDEN_TEXT, "session_id": session_id},
    )
    assert contract.status_code == 403

    guidance = await client.get("/api/policy/workflow-guidance/procurement")
    assert guidance.status_code == 200
    assert guidance.json()["configured"] is False


@pytest.mark.asyncio
async def test_get_session_detail_returns_contract(client):
    classify = await client.post("/api/change/classify", json={"text": GOLDEN_TEXT})
    session_id = classify.json()["session_id"]
    contract = await client.post(
        "/api/contract/generate",
        json={"text": GOLDEN_TEXT, "session_id": session_id},
    )
    assert contract.status_code == 200

    detail = await client.get(f"/api/sessions/{session_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["id"] == session_id
    assert payload["contract_yaml"]
    assert "finance_approval_required" in payload["contract"]["required_behaviour"]
    assert payload["contract_approved"] is False

    missing = await client.get("/api/sessions/does-not-exist")
    assert missing.status_code == 404

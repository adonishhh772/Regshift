import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.main import app
from app.database import init_db, get_connection
from app.services.policy_seed import seed_demo_policies
from app.services.erpnext_implementor import (
    PURCHASE_ORDER_JS_RELATIVE,
    PURCHASE_ORDER_PY_RELATIVE,
    apply_change_contract_to_erpnext,
)
from app.services.implementation_graph import extend_graph_with_implementation
from app.models.schemas import GraphNode, GraphEdge

GOLDEN_TEXT = (
    "From next quarter, all purchase orders above £25,000 must require finance approval "
    "before supplier confirmation. The system must log who approved it and block "
    "confirmation if approval is missing."
)

PROCUREMENT_CONTRACT = {
    "domain": "procurement",
    "entity": "purchase_order",
    "trigger": {"condition": "total_amount > 25000"},
    "required_behaviour": [
        "approval_event_logged",
        "finance_approval_required",
        "human_approval_required",
        "supplier_confirmation_blocked_until_approval",
    ],
    "approval_roles": ["Finance Manager", "Procurement Owner"],
    "policy_threshold": 25000,
}


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    connection = get_connection()
    connection.execute("DELETE FROM change_sessions")
    connection.commit()
    connection.close()
    seed_demo_policies()
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.fixture
def erpnext_sandbox(tmp_path, monkeypatch):
    repo_path = tmp_path / "erpnext"
    monkeypatch.setattr(settings, "erpnext_repo_path", repo_path)
    return repo_path


def test_apply_purchase_order_patches_creates_scaffold_and_markers(erpnext_sandbox):
    session = {
        "domain": "procurement",
        "contract_yaml": yaml.safe_dump(PROCUREMENT_CONTRACT),
    }

    result = apply_change_contract_to_erpnext(session)

    assert result["applied"] is True
    assert len(result["patches"]) == 3

    py_path = erpnext_sandbox / PURCHASE_ORDER_PY_RELATIVE
    js_path = erpnext_sandbox / PURCHASE_ORDER_JS_RELATIVE

    py_content = py_path.read_text(encoding="utf-8")
    js_content = js_path.read_text(encoding="utf-8")

    assert "REGSHIFT:BEGIN procurement_finance_approval" in py_content
    assert "regshift_validate_finance_approval(self)" in py_content
    assert "REGSHIFT_FINANCE_APPROVAL_THRESHOLD = 25000" in py_content
    assert "REGSHIFT:BEGIN supplier_confirmation_gate" in js_content
    assert "regshift_can_confirm_supplier(frm)" in js_content


def test_apply_is_idempotent_on_second_run(erpnext_sandbox):
    session = {
        "domain": "procurement",
        "contract_yaml": yaml.safe_dump(PROCUREMENT_CONTRACT),
    }

    first = apply_change_contract_to_erpnext(session)
    second = apply_change_contract_to_erpnext(session)

    assert first["applied"] is True
    assert second["applied"] is False
    assert second["patches"] == []


def test_extend_graph_adds_implementation_nodes():
    base_graph = {
        "nodes": [
            GraphNode(
                id="change_contract",
                label="Change Contract",
                type="ChangeContract",
                metadata={"domain": "procurement"},
            ).model_dump(),
            GraphNode(
                id="obligation_0",
                label="finance approval required",
                type="Obligation",
                metadata={"rule": "finance_approval_required"},
            ).model_dump(),
            GraphNode(
                id="file_0",
                label="purchase_order.py",
                type="File",
                metadata={"path": "erpnext/buying/doctype/purchase_order/purchase_order.py"},
            ).model_dump(),
        ],
        "edges": [
            GraphEdge(
                id="edge_0",
                source="change_contract",
                target="obligation_0",
                label="CONTAINS_OBLIGATION",
                type="CONTAINS_OBLIGATION",
            ).model_dump(),
        ],
    }

    patches = [
        {
            "patch_id": "patch_procurement_finance_approval",
            "file_path": "erpnext/buying/doctype/purchase_order/purchase_order.py",
            "obligation": "procurement_finance_approval",
            "change_type": "python",
            "description": "Finance approval gate",
            "lines_added": 40,
        }
    ]

    extended = extend_graph_with_implementation(base_graph, patches, pack_id="change_pack_test")

    node_types = {node.type for node in extended["nodes"]}
    assert "ImplementationPlan" in node_types
    assert "CodeChange" in node_types
    assert len(extended["nodes"]) >= len(base_graph["nodes"]) + 2

    edge_labels = {edge.label for edge in extended["edges"]}
    assert "REALIZED_BY" in edge_labels
    assert "MODIFIES" in edge_labels
    assert "IMPLEMENTS" in edge_labels


@pytest.mark.asyncio
async def test_implement_apply_endpoint(client, erpnext_sandbox):
    classify = await client.post("/api/change/classify", json={"text": GOLDEN_TEXT})
    session_id = classify.json()["session_id"]

    contract = await client.post(
        "/api/contract/generate",
        json={"text": GOLDEN_TEXT, "session_id": session_id},
    )
    await client.post(
        "/api/contract/approve",
        json={"session_id": session_id, "contract_yaml": contract.json()["contract_yaml"]},
    )
    await client.post("/api/index/scan")
    await client.post("/api/impact/analyze", json={"session_id": session_id})
    await client.post("/api/risk/score", json={"session_id": session_id})
    await client.post(f"/api/tests/generate?session_id={session_id}")
    await client.post(f"/api/simulation/run?session_id={session_id}")
    governance = await client.get(f"/api/governance/evaluate?session_id={session_id}")
    assert governance.json()["passed"] is True
    pack = await client.post("/api/pack/generate", json={"session_id": session_id})
    assert pack.status_code == 200

    response = await client.post("/api/implement/apply", json={"session_id": session_id})
    assert response.status_code == 200
    payload = response.json()
    assert payload["applied"] is True
    assert len(payload["patches"]) >= 1
    assert payload["graph"]["nodes"]
    assert any(node["type"] == "ImplementationPlan" for node in payload["graph"]["nodes"])

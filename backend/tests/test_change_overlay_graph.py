from pathlib import Path

import pytest

from app.database import get_connection, init_db
from app.models.schemas import ImpactedFile
from app.services.change_overlay_graph import (
    OVERLAY_EDGE_IMPACTS_KG,
    OVERLAY_NODE_SYSTEM_KG,
    apply_change_overlay,
)
from app.services.graph_builder import build_graph
from app.services.system_graph_builder import build_system_graph
from app.services.system_graph_store import lookup_kg_file_node, persist_system_graph


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    connection = get_connection()
    connection.execute("DELETE FROM system_graph_nodes")
    connection.execute("DELETE FROM system_graph_edges")
    connection.execute("DELETE FROM registered_systems")
    connection.commit()
    connection.close()
    yield


def test_apply_change_overlay_links_obligations_to_kg_nodes(tmp_path: Path):
    repo_path = tmp_path / "erpnext"
    relative_path = "erpnext/buying/doctype/purchase_order/purchase_order.py"
    target = repo_path / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "class PurchaseOrder:\n    def validate_finance_approval_for_high_value_orders(self):\n        return True\n",
        encoding="utf-8",
    )

    system = {"id": "erpnext", "name": "ERPNext", "vendor": "frappe", "connector": "generic_git"}
    graph = build_system_graph(system, repo_path)
    persist_system_graph("erpnext", graph)

    kg_match = lookup_kg_file_node("erpnext", relative_path)
    assert kg_match is not None

    contract = {
        "domain": "procurement",
        "required_behaviour": ["finance_approval_required", "supplier_confirmation_blocked_until_approval"],
        "approval_roles": ["Finance Manager"],
    }
    impact = {
        "processes": ["FinanceApprovalGate"],
        "modules": ["buying"],
        "files": [
            ImpactedFile(
                path=f"erpnext:{relative_path}",
                module="buying",
                score=42.0,
                evidence_snippet="finance approval purchase order",
                keywords=["finance", "purchase"],
                symbols=["validate_finance_approval_for_high_value_orders"],
            )
        ],
        "target_systems": ["erpnext"],
        "impact_source": "system_kg",
    }

    base_graph = build_graph(
        "Purchase order above 25000 requires finance approval",
        contract,
        impact,
        {"financial_control": "high"},
        [{"name": "test_finance_gate", "contract_rule": "finance_approval_required"}],
    )
    overlay_graph = apply_change_overlay(base_graph, contract, impact)

    overlay_nodes = [node for node in overlay_graph["nodes"] if node.type == OVERLAY_NODE_SYSTEM_KG]
    assert len(overlay_nodes) == 2
    assert overlay_nodes[0].metadata.get("kg_node_id") == kg_match["id"]
    assert overlay_nodes[0].metadata.get("impact_source") == "system_kg"

    overlay_edges = [edge for edge in overlay_graph["edges"] if edge.type == OVERLAY_EDGE_IMPACTS_KG]
    assert len(overlay_edges) == 2
    assert overlay_edges[0].source == "obligation_0"

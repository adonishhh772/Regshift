from pathlib import Path

import pytest

from app.services.system_metadata_builder import build_metadata_export_graph
from app.services.system_graph_store import persist_system_graph, search_impacted_files


@pytest.fixture
def salesforce_export(tmp_path: Path) -> Path:
    export_path = tmp_path / "salesforce"
    (export_path / "classes").mkdir(parents=True)
    (export_path / "metadata-manifest.json").write_text(
        """
        {
          "objects": [{"apiName": "Purchase_Order__c", "label": "Purchase Order", "description": "Finance approval purchase order"}],
          "classes": [{"name": "PurchaseOrderApproval", "methods": ["requiresFinanceApproval"], "description": "Finance approval apex"}],
          "flows": [{"name": "Finance_Approval_Flow", "label": "Finance Approval Flow", "description": "Supplier confirmation gate"}]
        }
        """,
        encoding="utf-8",
    )
    (export_path / "classes" / "PurchaseOrderApproval.cls").write_text(
        "public class PurchaseOrderApproval { public static Boolean requiresFinanceApproval() { return true; } }",
        encoding="utf-8",
    )
    return export_path


@pytest.fixture
def sap_export(tmp_path: Path) -> Path:
    export_path = tmp_path / "sap"
    export_path.mkdir()
    (export_path / "metadata-manifest.json").write_text(
        """
        {
          "modules": [{"name": "MM", "label": "Materials Management", "description": "Procurement purchase order module"}],
          "bapis": [{"name": "BAPI_PO_CREATE1", "module": "MM", "description": "Create purchase order with finance approval"}],
          "tables": [{"name": "EKKO", "module": "MM", "description": "Purchase order header approval status"}]
        }
        """,
        encoding="utf-8",
    )
    return export_path


def test_build_salesforce_metadata_graph(salesforce_export: Path):
    system = {"id": "salesforce-crm", "name": "Salesforce CRM", "vendor": "salesforce", "connector": "metadata_export"}
    graph = build_metadata_export_graph(system, salesforce_export)
    assert graph["file_count"] >= 3
    node_types = {node.type for node in graph["nodes"]}
    assert "Artifact" in node_types
    assert "CodeFile" in node_types


def test_build_sap_metadata_graph(sap_export: Path):
    system = {"id": "sap-s4", "name": "SAP S/4HANA", "vendor": "sap", "connector": "metadata_export"}
    graph = build_metadata_export_graph(system, sap_export)
    assert graph["file_count"] >= 3
    result = persist_system_graph("sap-s4", graph)
    assert result["node_count"] > 0
    matches = search_impacted_files(["sap-s4"], ["purchase", "finance", "approval"], limit=5)
    assert matches
    assert matches[0]["system_id"] == "sap-s4"

import pytest
import yaml
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import get_connection, init_db
from app.main import app
from app.services.policy_seed import seed_demo_policies
from app.services.system_graph_builder import build_system_graph
from app.services.system_graph_store import persist_system_graph, search_impacted_files
from app.services.system_identifier import identify_systems
from app.services.system_ingestor import ingest_system


@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    connection = get_connection()
    connection.execute("DELETE FROM change_sessions")
    connection.execute("DELETE FROM registered_systems")
    connection.execute("DELETE FROM system_graph_nodes")
    connection.execute("DELETE FROM system_graph_edges")
    connection.commit()
    connection.close()
    seed_demo_policies()
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


def test_identify_systems_for_procurement_text():
    result = identify_systems(
        "ERPNext purchase order above 25000 needs finance approval before supplier confirmation",
        "procurement",
    )
    system_ids = [item["system_id"] for item in result["systems"]]
    assert "erpnext" in system_ids
    assert result["primary_system_id"] == "erpnext"


def test_build_and_persist_system_graph(tmp_path):
    repo_path = tmp_path / "sample-system"
    repo_path.mkdir()
    (repo_path / "app").mkdir()
    (repo_path / "app" / "service.py").write_text(
        "class PurchaseOrderService:\n    def validate_finance_approval(self):\n        return True\n",
        encoding="utf-8",
    )
    system = {
        "id": "sample-system",
        "name": "Sample System",
        "vendor": "internal",
        "connector": "generic_git",
    }
    graph = build_system_graph(system, repo_path)
    assert graph["file_count"] == 1
    result = persist_system_graph("sample-system", graph)
    assert result["node_count"] > 1
    matches = search_impacted_files(["sample-system"], ["purchase", "finance"], limit=5)
    assert matches
    assert matches[0]["system_id"] == "sample-system"


@pytest.mark.asyncio
async def test_systems_api_and_classify(client, tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.yaml"
    catalog_path.write_text(
        yaml.safe_dump(
            {
                "systems": [
                    {
                        "id": "erpnext",
                        "name": "ERPNext",
                        "vendor": "frappe",
                        "connector": "generic_git",
                        "domains": ["procurement"],
                        "keywords": ["erpnext", "purchase order"],
                        "source": {"type": "git", "path": "sample"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    sample_repo = tmp_path / "sample"
    sample_repo.mkdir()
    (sample_repo / "purchase_order.py").write_text("class PurchaseOrder:\n    pass\n", encoding="utf-8")

    monkeypatch.setattr(settings, "systems_catalog_path", catalog_path)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    init_db()

    ingest = await client.post("/api/systems/erpnext/ingest")
    assert ingest.status_code == 200
    assert ingest.json()["persisted"] is True

    systems = await client.get("/api/systems")
    assert systems.status_code == 200
    assert systems.json()["total"] == 1

    classify = await client.post(
        "/api/change/classify",
        json={"text": "ERPNext purchase order finance approval above 25000"},
    )
    assert classify.status_code == 200
    payload = classify.json()
    assert payload["systems"]["primary_system_id"] == "erpnext"

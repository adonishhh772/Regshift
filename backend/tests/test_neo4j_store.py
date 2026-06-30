import json

import pytest

from app.models.schemas import GraphEdge, GraphNode
from app.services.neo4j_store import (
    _deserialize_graph_metadata,
    _serialize_graph_metadata,
    persist_session_graph,
)


def test_serialize_graph_metadata_preserves_nested_layout_fields():
    metadata = {
        "text": "Purchase order finance approval change",
        "x": 120.0,
        "y": 260,
        "score": 4.5,
    }

    serialized = _serialize_graph_metadata(metadata)
    restored = _deserialize_graph_metadata(serialized)

    assert restored == metadata


def test_deserialize_graph_metadata_accepts_legacy_dict():
    legacy = {"path": "erpnext/buying/doctype/purchase_order.py", "score": 3.2}
    assert _deserialize_graph_metadata(legacy) == legacy


@pytest.mark.parametrize(
    "raw_metadata",
    [None, "", "not-json", "[]"],
)
def test_deserialize_graph_metadata_handles_invalid_values(raw_metadata):
    assert _deserialize_graph_metadata(raw_metadata) == {}


def test_persist_session_graph_serializes_metadata_for_neo4j(monkeypatch):
    captured_metadata: list[str] = []

    class FakeResult:
        def data(self):
            return []

    class FakeSession:
        def run(self, query, **params):
            if "metadata" in params:
                captured_metadata.append(params["metadata"])
            return FakeResult()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeDriver:
        def session(self):
            return FakeSession()

    monkeypatch.setattr("app.services.neo4j_store._get_driver", lambda: FakeDriver())

    nodes = [
        GraphNode(
            id="business_change",
            label="Business Change",
            type="BusinessChange",
            metadata={"text": "Example change", "x": 0.0, "y": 0},
        )
    ]
    edges = [
        GraphEdge(
            id="edge_0",
            source="business_change",
            target="change_contract",
            label="COMPILED_INTO",
            type="COMPILED_INTO",
        )
    ]

    result = persist_session_graph("session-test", nodes, edges)

    assert result["persisted"] is True
    assert len(captured_metadata) == 1
    parsed = json.loads(captured_metadata[0])
    assert parsed["x"] == 0.0
    assert parsed["y"] == 0

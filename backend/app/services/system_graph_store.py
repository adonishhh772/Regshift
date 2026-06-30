import json
from datetime import datetime, timezone
from typing import Any

from app.database import get_connection
from app.models.schemas import GraphEdge, GraphNode
from app.services.neo4j_store import _get_driver
from app.services.system_constants import INGEST_STATUS_PENDING, INGEST_STATUS_READY, SYSTEM_NODE_ARTIFACT, SYSTEM_NODE_FILE

METADATA_JSON = "metadata_json"


def persist_system_graph(system_id: str, graph: dict[str, Any]) -> dict[str, Any]:
    nodes: list[GraphNode] = graph["nodes"]
    edges: list[GraphEdge] = graph["edges"]
    _persist_system_graph_sqlite(system_id, graph, nodes, edges)
    neo4j_result = _persist_system_graph_neo4j(system_id, nodes, edges)
    backend = neo4j_result.get("backend", "sqlite")
    return {
        "system_id": system_id,
        "persisted": True,
        "backend": backend,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "file_count": graph.get("file_count", 0),
        "last_ingest": graph.get("ingested_at"),
    }


def get_system_ingest_status(system_id: str) -> dict[str, Any]:
    connection = get_connection()
    row = connection.execute(
        "SELECT * FROM registered_systems WHERE id = ?",
        (system_id,),
    ).fetchone()
    connection.close()
    if row is None:
        return {"status": INGEST_STATUS_PENDING, "file_count": 0, "node_count": 0, "edge_count": 0}
    return {
        "status": row["ingest_status"],
        "file_count": row["file_count"],
        "node_count": row["node_count"],
        "edge_count": row["edge_count"],
        "last_ingest": row["last_ingest"],
    }


def lookup_kg_file_node(system_id: str, relative_path: str) -> dict[str, Any] | None:
    normalized = relative_path.replace("\\", "/").strip()
    if not system_id or not normalized:
        return None

    node_id = f"file::{system_id}::{normalized}"
    connection = get_connection()
    row = connection.execute(
        """
        SELECT id, system_id, label, type, metadata_json
        FROM system_graph_nodes
        WHERE id = ?
        """,
        (node_id,),
    ).fetchone()
    if row is None:
        basename = normalized.split("/")[-1]
        row = connection.execute(
            """
            SELECT id, system_id, label, type, metadata_json
            FROM system_graph_nodes
            WHERE system_id = ? AND type = ? AND (
                metadata_json LIKE ? OR metadata_json LIKE ? OR label = ?
            )
            LIMIT 1
            """,
            (system_id, SYSTEM_NODE_FILE, f'%"path": "{normalized}"%', f'%"path": "{basename}"%', basename),
        ).fetchone()
    connection.close()
    if row is None:
        return None

    metadata = _load_metadata(row["metadata_json"])
    return {
        "id": row["id"],
        "system_id": row["system_id"],
        "label": row["label"],
        "type": row["type"],
        "path": metadata.get("path", normalized),
        "snippet": metadata.get("snippet", ""),
        "package": metadata.get("package"),
    }


def search_impacted_files(
    system_ids: list[str],
    keywords: list[str],
    limit: int = 15,
) -> list[dict[str, Any]]:
    if not system_ids:
        return []
    keyword_set = {keyword.lower() for keyword in keywords if keyword.strip()}
    if not keyword_set:
        return []

    connection = get_connection()
    placeholders = ",".join("?" for _ in system_ids)
    rows = connection.execute(
        f"""
        SELECT id, system_id, label, type, metadata_json
        FROM system_graph_nodes
        WHERE system_id IN ({placeholders}) AND type IN (?, ?)
        """,
        (*system_ids, SYSTEM_NODE_FILE, SYSTEM_NODE_ARTIFACT),
    ).fetchall()
    connection.close()

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        metadata = _load_metadata(row["metadata_json"])
        haystack = " ".join(
            [
                row["label"],
                str(metadata.get("path", "")),
                str(metadata.get("snippet", "")),
                str(metadata.get("package", "")),
            ]
        ).lower()
        matched = [keyword for keyword in keyword_set if keyword in haystack]
        if not matched:
            continue
        score = len(matched) * 10.0
        if "purchase_order" in haystack:
            score += 20.0
        scored.append(
            (
                score,
                {
                    "path": metadata.get("path", row["label"]),
                    "module": metadata.get("package", "unknown"),
                    "score": score,
                    "content_snippet": metadata.get("snippet", ""),
                    "matched_keywords": matched,
                    "python_functions": "[]",
                    "python_classes": "[]",
                    "system_id": row["system_id"],
                },
            )
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:limit]]


def load_system_graph(system_id: str | None = None, limit: int = 500) -> dict[str, Any]:
    connection = get_connection()
    if system_id:
        node_rows = connection.execute(
            """
            SELECT id, system_id, label, type, metadata_json
            FROM system_graph_nodes
            WHERE system_id = ?
            ORDER BY id
            LIMIT ?
            """,
            (system_id, limit),
        ).fetchall()
        edge_rows = connection.execute(
            """
            SELECT id, system_id, source_id, target_id, label, type
            FROM system_graph_edges
            WHERE system_id = ?
            ORDER BY id
            LIMIT ?
            """,
            (system_id, limit * 2),
        ).fetchall()
    else:
        node_rows = connection.execute(
            """
            SELECT id, system_id, label, type, metadata_json
            FROM system_graph_nodes
            ORDER BY system_id, id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        edge_rows = connection.execute(
            """
            SELECT id, system_id, source_id, target_id, label, type
            FROM system_graph_edges
            ORDER BY system_id, id
            LIMIT ?
            """,
            (limit * 2,),
        ).fetchall()
    connection.close()

    nodes = [
        GraphNode(
            id=row["id"],
            label=row["label"],
            type=row["type"],
            metadata=_load_metadata(row["metadata_json"]),
        )
        for row in node_rows
    ]
    edges = [
        GraphEdge(
            id=row["id"],
            source=row["source_id"],
            target=row["target_id"],
            label=row["label"] or "",
            type=row["type"] or "",
        )
        for row in edge_rows
    ]
    return {"nodes": nodes, "edges": edges}


def _persist_system_graph_sqlite(
    system_id: str,
    graph: dict[str, Any],
    nodes: list[GraphNode],
    edges: list[GraphEdge],
) -> None:
    connection = get_connection()
    connection.execute("DELETE FROM system_graph_nodes WHERE system_id = ?", (system_id,))
    connection.execute("DELETE FROM system_graph_edges WHERE system_id = ?", (system_id,))
    for node in nodes:
        connection.execute(
            """
            INSERT INTO system_graph_nodes (id, system_id, label, type, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                node.id,
                system_id,
                node.label,
                node.type,
                json.dumps(node.metadata),
            ),
        )
    for edge in edges:
        connection.execute(
            """
            INSERT INTO system_graph_edges (id, system_id, source_id, target_id, label, type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                edge.id,
                system_id,
                edge.source,
                edge.target,
                edge.label,
                edge.type,
            ),
        )
    connection.execute(
        """
        INSERT INTO registered_systems (id, name, vendor, connector, ingest_status, file_count, node_count, edge_count, last_ingest, config_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            ingest_status = excluded.ingest_status,
            file_count = excluded.file_count,
            node_count = excluded.node_count,
            edge_count = excluded.edge_count,
            last_ingest = excluded.last_ingest
        """,
        (
            system_id,
            graph.get("name", system_id),
            graph.get("vendor"),
            graph.get("connector"),
            INGEST_STATUS_READY,
            graph.get("file_count", 0),
            len(nodes),
            len(edges),
            graph.get("ingested_at"),
            json.dumps({"system_id": system_id}),
        ),
    )
    connection.commit()
    connection.close()


def _persist_system_graph_neo4j(
    system_id: str,
    nodes: list[GraphNode],
    edges: list[GraphEdge],
) -> dict[str, Any]:
    driver = _get_driver()
    if driver is None:
        return {"persisted": False, "backend": "sqlite"}

    with driver.session() as session:
        session.run(
            """
            MATCH (n:SystemNode {system_id: $system_id})
            DETACH DELETE n
            """,
            system_id=system_id,
        )
        for node in nodes:
            session.run(
                """
                MERGE (n:SystemNode {id: $id, system_id: $system_id})
                SET n.label = $label, n.type = $type, n.metadata = $metadata
                WITH n
                MERGE (s:System {id: $system_id})
                MERGE (s)-[:CONTAINS]->(n)
                """,
                id=node.id,
                system_id=system_id,
                label=node.label,
                type=node.type,
                metadata=json.dumps(node.metadata),
            )
        for edge in edges:
            session.run(
                """
                MATCH (source:SystemNode {id: $source, system_id: $system_id})
                MATCH (target:SystemNode {id: $target, system_id: $system_id})
                MERGE (source)-[rel:SYSTEM_EDGE {id: $id}]->(target)
                SET rel.label = $label, rel.type = $type
                """,
                source=edge.source,
                target=edge.target,
                system_id=system_id,
                id=edge.id,
                label=edge.label,
                type=edge.type,
            )
    return {"persisted": True, "backend": "neo4j"}


def _load_metadata(raw_metadata: str | None) -> dict[str, Any]:
    if not raw_metadata:
        return {}
    try:
        parsed = json.loads(raw_metadata)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}

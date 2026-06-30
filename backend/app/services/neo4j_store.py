from typing import Any
import json

from app.config import settings
from app.models.schemas import GraphEdge, GraphNode

_driver = None
_neo4j_available: bool | None = None


def _serialize_graph_metadata(metadata: dict[str, Any]) -> str:
    return json.dumps(metadata)


def _deserialize_graph_metadata(raw_metadata: Any) -> dict[str, Any]:
    if raw_metadata is None:
        return {}
    if isinstance(raw_metadata, dict):
        return raw_metadata
    if isinstance(raw_metadata, str):
        try:
            parsed = json.loads(raw_metadata)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _get_driver():
    global _driver, _neo4j_available
    if not settings.neo4j_enabled:
        _neo4j_available = False
        return None
    if _neo4j_available is False:
        return None
    try:
        if _driver is None:
            from neo4j import GraphDatabase

            _driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
                connection_timeout=5.0,
            )
            _driver.verify_connectivity()
            _neo4j_available = True
        return _driver
    except Exception:
        _neo4j_available = False
        _driver = None
        return None


def probe_neo4j_connectivity() -> None:
    _get_driver()


def neo4j_status() -> dict[str, Any]:
    if not settings.neo4j_enabled:
        return {"available": False, "backend": "networkx_fallback"}
    if _neo4j_available is True and _driver is not None:
        return {"available": True, "backend": "neo4j", "uri": settings.neo4j_uri}
    return {"available": False, "backend": "networkx_fallback"}


def persist_session_graph(session_id: str, nodes: list[GraphNode], edges: list[GraphEdge]) -> dict[str, Any]:
    driver = _get_driver()
    if driver is None:
        return {"persisted": False, "backend": "networkx_fallback", "node_count": len(nodes)}

    with driver.session() as session:
        session.run(
            """
            MERGE (s:ChangeSession {id: $session_id})
            SET s.updated_at = datetime()
            WITH s
            OPTIONAL MATCH (n:GraphNode {session_id: $session_id})
            DETACH DELETE n
            """,
            session_id=session_id,
        )

        for node in nodes:
            session.run(
                """
                CREATE (n:GraphNode {
                    id: $id,
                    session_id: $session_id,
                    label: $label,
                    type: $type,
                    status: $status
                })
                SET n.metadata = $metadata
                WITH n
                MATCH (s:ChangeSession {id: $session_id})
                MERGE (s)-[:HAS_NODE]->(n)
                """,
                id=node.id,
                session_id=session_id,
                label=node.label,
                type=node.type,
                status=node.status,
                metadata=_serialize_graph_metadata(node.metadata),
            )

        for edge in edges:
            session.run(
                """
                MATCH (source:GraphNode {id: $source, session_id: $session_id})
                MATCH (target:GraphNode {id: $target, session_id: $session_id})
                MERGE (source)-[rel:IMPACT_EDGE {id: $id}]->(target)
                SET rel.label = $label, rel.type = $type
                """,
                source=edge.source,
                target=edge.target,
                session_id=session_id,
                id=edge.id,
                label=edge.label,
                type=edge.type,
            )

    return {"persisted": True, "backend": "neo4j", "node_count": len(nodes), "edge_count": len(edges)}


def load_session_graph(session_id: str) -> dict[str, Any] | None:
    driver = _get_driver()
    if driver is None:
        return None

    with driver.session() as session:
        node_rows = session.run(
            """
            MATCH (n:GraphNode {session_id: $session_id})
            RETURN n.id AS id, n.label AS label, n.type AS type, n.status AS status, n.metadata AS metadata
            ORDER BY n.id
            """,
            session_id=session_id,
        ).data()

        edge_rows = session.run(
            """
            MATCH (source:GraphNode {session_id: $session_id})-[rel:IMPACT_EDGE]->(target:GraphNode {session_id: $session_id})
            RETURN rel.id AS id, source.id AS source, target.id AS target, rel.label AS label, rel.type AS type
            """,
            session_id=session_id,
        ).data()

    if not node_rows:
        return None

    nodes = [
        GraphNode(
            id=row["id"],
            label=row["label"],
            type=row["type"],
            status=row.get("status") or "completed",
            metadata=_deserialize_graph_metadata(row.get("metadata")),
        )
        for row in node_rows
    ]
    edges = [
        GraphEdge(
            id=row["id"],
            source=row["source"],
            target=row["target"],
            label=row.get("label") or "",
            type=row.get("type") or "",
        )
        for row in edge_rows
    ]
    return {"nodes": nodes, "edges": edges}


def trace_obligation_path(session_id: str, obligation_node_id: str) -> list[str]:
    driver = _get_driver()
    if driver is None:
        return []

    with driver.session() as session:
        rows = session.run(
            """
            MATCH path = (start:GraphNode {id: $obligation_id, session_id: $session_id})
              -[:IMPACT_EDGE*1..8]->(end:GraphNode)
            WHERE start.type = 'Obligation'
            RETURN [node IN nodes(path) | node.id] AS path_ids, length(path) AS path_length
            ORDER BY path_length DESC
            LIMIT 1
            """,
            session_id=session_id,
            obligation_id=obligation_node_id,
        ).data()

    if not rows:
        return [obligation_node_id]
    return rows[0]["path_ids"]

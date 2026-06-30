import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import init_db, session_store
from app.services.erpnext_implementor import apply_change_contract_to_erpnext
from app.services.implementation_graph import extend_graph_with_implementation
from app.services.neo4j_store import persist_session_graph

PACK_SUFFIX = sys.argv[1] if len(sys.argv) > 1 else "215246"


def main() -> None:
    init_db()
    db_path = Path(__file__).resolve().parents[2] / "data" / "regshift.db"
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT * FROM change_sessions WHERE pack_id LIKE ? ORDER BY updated_at DESC LIMIT 1",
        (f"%{PACK_SUFFIX}%",),
    ).fetchone()
    if row is None:
        row = connection.execute(
            "SELECT * FROM change_sessions WHERE pack_id IS NOT NULL ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    connection.close()

    if row is None:
        print("No session with change pack found.")
        return

    session = dict(row)
    print(f"Session: {session['id']}")
    print(f"Pack: {session.get('pack_id')}")

    result = apply_change_contract_to_erpnext(session)
    graph_data = json.loads(session.get("graph_json") or '{"nodes": [], "edges": []}')
    extended = extend_graph_with_implementation(
        graph_data,
        result.get("patches", []),
        pack_id=session.get("pack_id"),
    )

    session_store.update_session(
        session["id"],
        graph_json=json.dumps(
            {
                "nodes": [node.model_dump() for node in extended["nodes"]],
                "edges": [edge.model_dump() for edge in extended["edges"]],
            }
        ),
        implementation_json=json.dumps(result),
    )
    neo4j_result = persist_session_graph(session["id"], extended["nodes"], extended["edges"])

    print(f"Applied: {result['applied']}")
    print(f"Repo: {result['repo_path']}")
    print(f"Patches: {len(result['patches'])}")
    for patch in result["patches"]:
        print(f"  - {patch['file_path']} ({patch['patch_id']})")
    print(f"Graph: {len(extended['nodes'])} nodes, {len(extended['edges'])} edges")
    print(f"Neo4j: {neo4j_result}")


if __name__ == "__main__":
    main()

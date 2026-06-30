from typing import Any

from pathlib import Path

from app.services.system_catalog import (
    ensure_workspace_repo_links,
    get_system_by_id,
    load_system_catalog,
    resolve_system_source_path,
)
from app.services.system_constants import INGEST_STATUS_FAILED, INGEST_STATUS_MISSING
from app.services.system_constants import CONNECTOR_GENERIC_GIT, CONNECTOR_METADATA_EXPORT
from app.services.system_graph_builder import build_system_graph
from app.services.system_graph_store import persist_system_graph
from app.services.system_metadata_builder import build_metadata_export_graph


def ingest_all_systems() -> dict[str, Any]:
    ensure_workspace_repo_links()
    results: list[dict[str, Any]] = []
    for system in load_system_catalog():
        results.append(ingest_system(str(system["id"])))
    succeeded = sum(1 for result in results if result.get("persisted"))
    return {
        "total": len(results),
        "succeeded": succeeded,
        "results": results,
    }


def ingest_system(system_id: str) -> dict[str, Any]:
    ensure_workspace_repo_links()
    system = get_system_by_id(system_id)
    if system is None:
        return {
            "system_id": system_id,
            "persisted": False,
            "reason": f"Unknown system '{system_id}'",
            "status": INGEST_STATUS_FAILED,
        }

    source_path = resolve_system_source_path(system)
    if source_path is None or not source_path.exists():
        return {
            "system_id": system_id,
            "persisted": False,
            "reason": f"Source path missing for system '{system_id}'",
            "status": INGEST_STATUS_MISSING,
            "source_path": str(source_path) if source_path else None,
        }

    _ensure_source_seed(system, source_path)
    connector = str(system.get("connector", CONNECTOR_GENERIC_GIT))
    try:
        if connector == CONNECTOR_METADATA_EXPORT:
            graph = build_metadata_export_graph(system, source_path)
        else:
            graph = build_system_graph(system, source_path)
        graph["name"] = system.get("name")
        graph["vendor"] = system.get("vendor")
        graph["connector"] = system.get("connector")
        result = persist_system_graph(system_id, graph)
    except Exception as error:
        return {
            "system_id": system_id,
            "persisted": False,
            "reason": str(error),
            "status": INGEST_STATUS_FAILED,
        }
    result["status"] = "ready" if result.get("persisted") else INGEST_STATUS_FAILED
    return result


def _ensure_source_seed(system: dict[str, Any], source_path: Path) -> None:
    system_id = str(system.get("id", ""))
    if system_id != "erpnext":
        return
    from app.services.erpnext_implementor import ensure_erpnext_kg_seed

    ensure_erpnext_kg_seed(source_path)

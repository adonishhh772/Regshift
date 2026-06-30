from pathlib import Path
from typing import Any

import yaml

from app.config import settings
from app.services.system_constants import CONNECTOR_GENERIC_GIT, SOURCE_TYPE_GIT

DEFAULT_CATALOG_RELATIVE = Path("systems") / "catalog.yaml"


def load_system_catalog() -> list[dict[str, Any]]:
    catalog_path = settings.systems_catalog_path
    if not catalog_path.exists():
        return []
    with catalog_path.open(encoding="utf-8") as catalog_file:
        payload = yaml.safe_load(catalog_file) or {}
    systems = payload.get("systems", [])
    if not isinstance(systems, list):
        return []
    return [system for system in systems if isinstance(system, dict) and system.get("id")]


def get_system_by_id(system_id: str) -> dict[str, Any] | None:
    for system in load_system_catalog():
        if system.get("id") == system_id:
            return system
    return None


def resolve_system_source_path(system: dict[str, Any]) -> Path | None:
    source = system.get("source") or {}
    if not isinstance(source, dict):
        return None
    raw_path = source.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (settings.data_dir / path).resolve()


def list_catalog_summaries() -> list[dict[str, Any]]:
    from app.services.system_graph_store import get_system_ingest_status

    summaries: list[dict[str, Any]] = []
    for system in load_system_catalog():
        system_id = str(system.get("id"))
        source_path = resolve_system_source_path(system)
        ingest_status = get_system_ingest_status(system_id)
        summaries.append(
            {
                "id": system_id,
                "name": system.get("name", system_id),
                "vendor": system.get("vendor", "unknown"),
                "connector": system.get("connector", CONNECTOR_GENERIC_GIT),
                "domains": list(system.get("domains") or []),
                "source_type": (system.get("source") or {}).get("type", SOURCE_TYPE_GIT),
                "source_path": str(source_path) if source_path else None,
                "source_available": bool(source_path and source_path.exists()),
                "ingest_status": ingest_status.get("status"),
                "file_count": ingest_status.get("file_count", 0),
                "node_count": ingest_status.get("node_count", 0),
                "edge_count": ingest_status.get("edge_count", 0),
                "last_ingest": ingest_status.get("last_ingest"),
            }
        )
    return summaries


def ensure_workspace_repo_links() -> None:
    backend_link = settings.data_dir / "repos" / "regshift-backend"
    frontend_link = settings.data_dir / "repos" / "regshift-frontend"
    repo_root = settings.data_dir.parent
    backend_source = repo_root / "backend"
    frontend_source = repo_root / "frontend"
    _ensure_directory_link(backend_link, backend_source)
    _ensure_directory_link(frontend_link, frontend_source)


def _ensure_directory_link(link_path: Path, target_path: Path) -> None:
    if not target_path.exists():
        return
    link_path.parent.mkdir(parents=True, exist_ok=True)
    if link_path.exists():
        return
    try:
        link_path.symlink_to(target_path, target_is_directory=True)
    except OSError:
        return

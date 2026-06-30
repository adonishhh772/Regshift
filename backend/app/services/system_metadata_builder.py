import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.schemas import GraphEdge, GraphNode
from app.services.system_constants import (
    EDGE_CONTAINS,
    EDGE_DEFINES,
    SYSTEM_NODE_ARTIFACT,
    SYSTEM_NODE_FILE,
    SYSTEM_NODE_PACKAGE,
    SYSTEM_NODE_SYMBOL,
    SYSTEM_NODE_SYSTEM,
)

MANIFEST_FILENAME = "metadata-manifest.json"
SALESFORCE_VENDOR = "salesforce"
SAP_VENDOR = "sap"


def build_metadata_export_graph(system: dict[str, Any], source_path: Path) -> dict[str, Any]:
    vendor = str(system.get("vendor", "")).lower()
    if vendor == SALESFORCE_VENDOR:
        return _build_salesforce_graph(system, source_path)
    if vendor == SAP_VENDOR:
        return _build_sap_graph(system, source_path)
    return _build_manifest_graph(system, source_path)


def _build_salesforce_graph(system: dict[str, Any], source_path: Path) -> dict[str, Any]:
    system_id = str(system["id"])
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    edge_index = 0
    file_count = 0

    system_node_id = f"system::{system_id}"
    nodes.append(
        GraphNode(
            id=system_node_id,
            label=str(system.get("name", system_id)),
            type=SYSTEM_NODE_SYSTEM,
            metadata={"system_id": system_id, "vendor": SALESFORCE_VENDOR, "connector": "metadata_export"},
        )
    )

    manifest = _load_manifest(source_path)
    package_map: dict[str, str] = {}

    for object_entry in manifest.get("objects", []):
        if not isinstance(object_entry, dict):
            continue
        api_name = str(object_entry.get("apiName", object_entry.get("name", "UnknownObject")))
        package_id, edge_index = _ensure_package(
            system_id, "Salesforce Objects", package_map, nodes, edges, edge_index, system_node_id
        )
        artifact_id = f"artifact::{system_id}::object::{api_name}"
        label = str(object_entry.get("label", api_name))
        nodes.append(
            GraphNode(
                id=artifact_id,
                label=label,
                type=SYSTEM_NODE_ARTIFACT,
                metadata={
                    "system_id": system_id,
                    "artifact_type": "salesforce_object",
                    "api_name": api_name,
                    "path": f"objects/{api_name}.object",
                    "snippet": object_entry.get("description", label),
                },
            )
        )
        edges.append(
            GraphEdge(
                id=f"edge::{system_id}::{edge_index}",
                source=package_id,
                target=artifact_id,
                label=EDGE_CONTAINS,
                type=EDGE_CONTAINS,
            )
        )
        edge_index += 1
        file_count += 1

    for class_entry in manifest.get("classes", []):
        if not isinstance(class_entry, dict):
            continue
        class_name = str(class_entry.get("name", "UnknownClass"))
        package_id, edge_index = _ensure_package(
            system_id, "Apex Classes", package_map, nodes, edges, edge_index, system_node_id
        )
        relative_path = f"classes/{class_name}.cls"
        class_path = source_path / relative_path
        body = class_path.read_text(encoding="utf-8", errors="ignore") if class_path.exists() else ""
        file_node_id = f"file::{system_id}::{relative_path}"
        nodes.append(
            GraphNode(
                id=file_node_id,
                label=class_name,
                type=SYSTEM_NODE_FILE,
                metadata={
                    "system_id": system_id,
                    "path": relative_path,
                    "extension": ".cls",
                    "snippet": (body or class_entry.get("description", class_name))[:500],
                    "package": "Apex Classes",
                },
            )
        )
        edges.append(
            GraphEdge(
                id=f"edge::{system_id}::{edge_index}",
                source=package_id,
                target=file_node_id,
                label=EDGE_CONTAINS,
                type=EDGE_CONTAINS,
            )
        )
        edge_index += 1
        file_count += 1

        for method_name in class_entry.get("methods", []):
            symbol_id = f"symbol::{system_id}::{class_name}::{method_name}"
            nodes.append(
                GraphNode(
                    id=symbol_id,
                    label=str(method_name),
                    type=SYSTEM_NODE_SYMBOL,
                    metadata={"system_id": system_id, "kind": "method", "class": class_name},
                )
            )
            edges.append(
                GraphEdge(
                    id=f"edge::{system_id}::{edge_index}",
                    source=file_node_id,
                    target=symbol_id,
                    label=EDGE_DEFINES,
                    type=EDGE_DEFINES,
                )
            )
            edge_index += 1

    for flow_entry in manifest.get("flows", []):
        if not isinstance(flow_entry, dict):
            continue
        flow_name = str(flow_entry.get("name", "UnknownFlow"))
        package_id, edge_index = _ensure_package(
            system_id, "Flows", package_map, nodes, edges, edge_index, system_node_id
        )
        artifact_id = f"artifact::{system_id}::flow::{flow_name}"
        nodes.append(
            GraphNode(
                id=artifact_id,
                label=str(flow_entry.get("label", flow_name)),
                type=SYSTEM_NODE_ARTIFACT,
                metadata={
                    "system_id": system_id,
                    "artifact_type": "salesforce_flow",
                    "path": f"flows/{flow_name}.flow-meta.xml",
                    "snippet": flow_entry.get("description", flow_name),
                },
            )
        )
        edges.append(
            GraphEdge(
                id=f"edge::{system_id}::{edge_index}",
                source=package_id,
                target=artifact_id,
                label=EDGE_CONTAINS,
                type=EDGE_CONTAINS,
            )
        )
        edge_index += 1
        file_count += 1

    return {
        "nodes": nodes,
        "edges": edges,
        "file_count": file_count,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_sap_graph(system: dict[str, Any], source_path: Path) -> dict[str, Any]:
    system_id = str(system["id"])
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    edge_index = 0
    file_count = 0

    system_node_id = f"system::{system_id}"
    nodes.append(
        GraphNode(
            id=system_node_id,
            label=str(system.get("name", system_id)),
            type=SYSTEM_NODE_SYSTEM,
            metadata={"system_id": system_id, "vendor": SAP_VENDOR, "connector": "metadata_export"},
        )
    )

    manifest = _load_manifest(source_path)
    package_map: dict[str, str] = {}

    for module_entry in manifest.get("modules", []):
        if not isinstance(module_entry, dict):
            continue
        module_name = str(module_entry.get("name", "MM"))
        package_id, edge_index = _ensure_package(
            system_id, f"SAP {module_name}", package_map, nodes, edges, edge_index, system_node_id
        )
        artifact_id = f"artifact::{system_id}::module::{module_name}"
        nodes.append(
            GraphNode(
                id=artifact_id,
                label=str(module_entry.get("label", module_name)),
                type=SYSTEM_NODE_ARTIFACT,
                metadata={
                    "system_id": system_id,
                    "artifact_type": "sap_module",
                    "path": f"modules/{module_name}.json",
                    "snippet": module_entry.get("description", module_name),
                },
            )
        )
        edges.append(
            GraphEdge(
                id=f"edge::{system_id}::{edge_index}",
                source=package_id,
                target=artifact_id,
                label=EDGE_CONTAINS,
                type=EDGE_CONTAINS,
            )
        )
        edge_index += 1
        file_count += 1

    for bapi_entry in manifest.get("bapis", []):
        if not isinstance(bapi_entry, dict):
            continue
        bapi_name = str(bapi_entry.get("name", "BAPI_UNKNOWN"))
        module_name = str(bapi_entry.get("module", "MM"))
        package_id, edge_index = _ensure_package(
            system_id, f"SAP {module_name}", package_map, nodes, edges, edge_index, system_node_id
        )
        artifact_id = f"artifact::{system_id}::bapi::{bapi_name}"
        nodes.append(
            GraphNode(
                id=artifact_id,
                label=bapi_name,
                type=SYSTEM_NODE_ARTIFACT,
                metadata={
                    "system_id": system_id,
                    "artifact_type": "sap_bapi",
                    "path": f"bapis/{bapi_name}.json",
                    "snippet": bapi_entry.get("description", bapi_name),
                },
            )
        )
        edges.append(
            GraphEdge(
                id=f"edge::{system_id}::{edge_index}",
                source=package_id,
                target=artifact_id,
                label=EDGE_CONTAINS,
                type=EDGE_CONTAINS,
            )
        )
        edge_index += 1
        file_count += 1

    for table_entry in manifest.get("tables", []):
        if not isinstance(table_entry, dict):
            continue
        table_name = str(table_entry.get("name", "UNKNOWN"))
        module_name = str(table_entry.get("module", "MM"))
        package_id, edge_index = _ensure_package(
            system_id, f"SAP {module_name}", package_map, nodes, edges, edge_index, system_node_id
        )
        artifact_id = f"artifact::{system_id}::table::{table_name}"
        nodes.append(
            GraphNode(
                id=artifact_id,
                label=table_name,
                type=SYSTEM_NODE_ARTIFACT,
                metadata={
                    "system_id": system_id,
                    "artifact_type": "sap_table",
                    "path": f"tables/{table_name}.json",
                    "snippet": table_entry.get("description", table_name),
                },
            )
        )
        edges.append(
            GraphEdge(
                id=f"edge::{system_id}::{edge_index}",
                source=package_id,
                target=artifact_id,
                label=EDGE_CONTAINS,
                type=EDGE_CONTAINS,
            )
        )
        edge_index += 1
        file_count += 1

    return {
        "nodes": nodes,
        "edges": edges,
        "file_count": file_count,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def _build_manifest_graph(system: dict[str, Any], source_path: Path) -> dict[str, Any]:
    return _build_salesforce_graph(system, source_path)


def _load_manifest(source_path: Path) -> dict[str, Any]:
    manifest_path = source_path / MANIFEST_FILENAME
    if not manifest_path.exists():
        return {}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _ensure_package(
    system_id: str,
    package_name: str,
    package_map: dict[str, str],
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    edge_index: int,
    system_node_id: str,
) -> tuple[str, int]:
    if package_name in package_map:
        return package_map[package_name], edge_index

    package_node_id = f"package::{system_id}::{package_name.replace(' ', '_').lower()}"
    package_map[package_name] = package_node_id
    nodes.append(
        GraphNode(
            id=package_node_id,
            label=package_name,
            type=SYSTEM_NODE_PACKAGE,
            metadata={"system_id": system_id, "package": package_name},
        )
    )
    edges.append(
        GraphEdge(
            id=f"edge::{system_id}::{edge_index}",
            source=system_node_id,
            target=package_node_id,
            label=EDGE_CONTAINS,
            type=EDGE_CONTAINS,
        )
    )
    return package_node_id, edge_index + 1

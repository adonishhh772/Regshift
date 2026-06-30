import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.schemas import GraphEdge, GraphNode
from app.services.system_constants import (
    EDGE_CONTAINS,
    EDGE_DEFINES,
    EDGE_IMPORTS,
    SYSTEM_NODE_ARTIFACT,
    SYSTEM_NODE_FILE,
    SYSTEM_NODE_PACKAGE,
    SYSTEM_NODE_SYMBOL,
    SYSTEM_NODE_SYSTEM,
)

SCAN_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".html", ".md", ".yml", ".yaml"}
IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "env", "dist", "build", ".next"}


def build_system_graph(system: dict[str, Any], source_path: Path) -> dict[str, Any]:
    system_id = str(system["id"])
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    edge_index = 0

    system_node_id = f"system::{system_id}"
    nodes.append(
        GraphNode(
            id=system_node_id,
            label=str(system.get("name", system_id)),
            type=SYSTEM_NODE_SYSTEM,
            metadata={
                "system_id": system_id,
                "vendor": system.get("vendor"),
                "connector": system.get("connector"),
            },
        )
    )

    package_nodes: dict[str, str] = {}

    for file_path in sorted(source_path.rglob("*")):
        if not file_path.is_file():
            continue
        if any(part in IGNORE_DIRS for part in file_path.parts):
            continue
        if file_path.suffix.lower() not in SCAN_EXTENSIONS:
            continue

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        relative_path = str(file_path.relative_to(source_path)).replace("\\", "/")
        package_name = _resolve_package_name(relative_path)
        package_node_id, edge_index = _ensure_package_node(
            system_id=system_id,
            package_name=package_name,
            package_nodes=package_nodes,
            nodes=nodes,
            edges=edges,
            edge_index=edge_index,
            system_node_id=system_node_id,
        )

        file_node_id = f"file::{system_id}::{relative_path}"
        snippet = content[:500].replace("\n", " ")
        nodes.append(
            GraphNode(
                id=file_node_id,
                label=Path(relative_path).name,
                type=SYSTEM_NODE_FILE,
                metadata={
                    "system_id": system_id,
                    "path": relative_path,
                    "extension": file_path.suffix,
                    "snippet": snippet,
                    "package": package_name,
                },
            )
        )
        edges.append(
            GraphEdge(
                id=f"edge_{system_id}_{edge_index}",
                source=package_node_id,
                target=file_node_id,
                label=EDGE_CONTAINS,
                type=EDGE_CONTAINS,
            )
        )
        edge_index += 1

        if relative_path.endswith(".json") and "/doctype/" in relative_path.lower():
            artifact_id = f"artifact::{system_id}::{relative_path}"
            nodes.append(
                GraphNode(
                    id=artifact_id,
                    label=Path(relative_path).parent.name,
                    type=SYSTEM_NODE_ARTIFACT,
                    metadata={
                        "system_id": system_id,
                        "artifact_type": "DocType",
                        "path": relative_path,
                    },
                )
            )
            edges.append(
                GraphEdge(
                    id=f"edge_{system_id}_{edge_index}",
                    source=file_node_id,
                    target=artifact_id,
                    label=EDGE_DEFINES,
                    type=EDGE_DEFINES,
                )
            )
            edge_index += 1

        if file_path.suffix == ".py":
            symbols, imports = _parse_python(content)
            seen_symbol_ids: set[str] = set()
            for symbol_name in symbols:
                symbol_id = f"symbol::{system_id}::{relative_path}::{symbol_name}"
                if symbol_id in seen_symbol_ids:
                    continue
                seen_symbol_ids.add(symbol_id)
                nodes.append(
                    GraphNode(
                        id=symbol_id,
                        label=symbol_name,
                        type=SYSTEM_NODE_SYMBOL,
                        metadata={
                            "system_id": system_id,
                            "path": relative_path,
                            "kind": "python_symbol",
                        },
                    )
                )
                edges.append(
                    GraphEdge(
                        id=f"edge_{system_id}_{edge_index}",
                        source=file_node_id,
                        target=symbol_id,
                        label=EDGE_DEFINES,
                        type=EDGE_DEFINES,
                    )
                )
                edge_index += 1
            for import_name in imports[:20]:
                import_id = f"import::{system_id}::{import_name}"
                if not any(node.id == import_id for node in nodes):
                    nodes.append(
                        GraphNode(
                            id=import_id,
                            label=import_name,
                            type=SYSTEM_NODE_PACKAGE,
                            metadata={"system_id": system_id, "kind": "import"},
                        )
                    )
                edges.append(
                    GraphEdge(
                        id=f"edge_{system_id}_{edge_index}",
                        source=file_node_id,
                        target=import_id,
                        label=EDGE_IMPORTS,
                        type=EDGE_IMPORTS,
                    )
                )
                edge_index += 1

    file_count = sum(1 for node in nodes if node.type == SYSTEM_NODE_FILE)
    return {
        "system_id": system_id,
        "nodes": nodes,
        "edges": edges,
        "file_count": file_count,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def _resolve_package_name(relative_path: str) -> str:
    parts = relative_path.split("/")
    if len(parts) >= 2:
        return parts[0]
    return "root"


def _ensure_package_node(
    system_id: str,
    package_name: str,
    package_nodes: dict[str, str],
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    edge_index: int,
    system_node_id: str,
) -> tuple[str, int]:
    if package_name in package_nodes:
        return package_nodes[package_name], edge_index
    package_node_id = f"package::{system_id}::{package_name}"
    package_nodes[package_name] = package_node_id
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
            id=f"edge_{system_id}_{edge_index}",
            source=system_node_id,
            target=package_node_id,
            label=EDGE_CONTAINS,
            type=EDGE_CONTAINS,
        )
    )
    return package_node_id, edge_index + 1


def _parse_python(content: str) -> tuple[list[str], list[str]]:
    symbols: list[str] = []
    imports: list[str] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return symbols, imports
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            symbols.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return symbols, imports

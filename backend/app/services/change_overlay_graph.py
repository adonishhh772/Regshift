from pathlib import Path
from typing import Any

from app.models.schemas import GraphEdge, GraphNode
from app.services.system_catalog import get_system_by_id
from app.services.system_graph_store import lookup_kg_file_node

OVERLAY_EDGE_IMPACTS_KG = "IMPACTS_KG"
OVERLAY_EDGE_TARGETS_SYSTEM = "TARGETS_SYSTEM"
OVERLAY_EDGE_IN_SYSTEM = "IN_SYSTEM"
OVERLAY_EDGE_RESOLVES_TO_KG = "RESOLVES_TO_KG"
OVERLAY_NODE_SYSTEM_KG = "SystemKGFile"
OVERLAY_NODE_TARGET_SYSTEM = "TargetSystem"


def apply_change_overlay(
    graph_data: dict[str, Any],
    contract: dict[str, Any],
    impact: dict[str, Any],
) -> dict[str, Any]:
    nodes: list[GraphNode] = list(graph_data["nodes"])
    edges: list[GraphEdge] = list(graph_data["edges"])
    edge_index = len(edges)

    target_systems = list(impact.get("target_systems") or [])
    target_node_ids = _add_target_system_nodes(nodes, edges, edge_index, target_systems)
    edge_index = len(edges)

    obligations = list(contract.get("required_behaviour") or [])
    raw_files = impact.get("files") or []

    for index, _obligation in enumerate(obligations):
        obligation_id = f"obligation_{index}"
        if not _node_exists(nodes, obligation_id):
            continue
        if not raw_files:
            continue

        file_entry = raw_files[index % len(raw_files)]
        path_value, score_value = _read_impact_file(file_entry)
        system_id, relative_path = _parse_impact_path(path_value, target_systems)
        kg_match = _resolve_kg_match(system_id, relative_path, target_systems)

        resolved_system_id = kg_match.get("system_id") if kg_match else system_id
        resolved_path = kg_match.get("path") if kg_match else relative_path or path_value
        overlay_id = f"system_kg_{index}"
        metadata: dict[str, Any] = {
            "system_id": resolved_system_id,
            "path": resolved_path,
            "kg_node_id": kg_match.get("id") if kg_match else None,
            "impact_source": impact.get("impact_source"),
        }
        if score_value is not None:
            metadata["score"] = score_value
        if kg_match:
            metadata["snippet"] = kg_match.get("snippet", "")

        nodes.append(
            GraphNode(
                id=overlay_id,
                label=_overlay_label(resolved_path or path_value),
                type=OVERLAY_NODE_SYSTEM_KG,
                metadata=metadata,
            )
        )
        edges.append(
            GraphEdge(
                id=f"edge_{edge_index}",
                source=obligation_id,
                target=overlay_id,
                label=OVERLAY_EDGE_IMPACTS_KG,
                type=OVERLAY_EDGE_IMPACTS_KG,
            )
        )
        edge_index += 1

        target_node_id = target_node_ids.get(resolved_system_id or "")
        if target_node_id:
            edges.append(
                GraphEdge(
                    id=f"edge_{edge_index}",
                    source=overlay_id,
                    target=target_node_id,
                    label=OVERLAY_EDGE_IN_SYSTEM,
                    type=OVERLAY_EDGE_IN_SYSTEM,
                )
            )
            edge_index += 1

        session_file_id = f"file_{index}"
        if _node_exists(nodes, session_file_id):
            edges.append(
                GraphEdge(
                    id=f"edge_{edge_index}",
                    source=session_file_id,
                    target=overlay_id,
                    label=OVERLAY_EDGE_RESOLVES_TO_KG,
                    type=OVERLAY_EDGE_RESOLVES_TO_KG,
                )
            )
            edge_index += 1

    return {"nodes": nodes, "edges": edges}


def _add_target_system_nodes(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    edge_index: int,
    target_systems: list[str],
) -> dict[str, str]:
    target_node_ids: dict[str, str] = {}
    for system_id in target_systems:
        node_id = f"target_system_{system_id}"
        if _node_exists(nodes, node_id):
            target_node_ids[system_id] = node_id
            continue
        system = get_system_by_id(system_id)
        label = str(system.get("name", system_id)) if system else system_id
        nodes.append(
            GraphNode(
                id=node_id,
                label=label,
                type=OVERLAY_NODE_TARGET_SYSTEM,
                metadata={"system_id": system_id},
            )
        )
        edges.append(
            GraphEdge(
                id=f"edge_{edge_index}",
                source="change_contract",
                target=node_id,
                label=OVERLAY_EDGE_TARGETS_SYSTEM,
                type=OVERLAY_EDGE_TARGETS_SYSTEM,
            )
        )
        edge_index += 1
        target_node_ids[system_id] = node_id
    return target_node_ids


def _resolve_kg_match(
    system_id: str | None,
    relative_path: str,
    target_systems: list[str],
) -> dict[str, Any] | None:
    if system_id and relative_path:
        match = lookup_kg_file_node(system_id, relative_path)
        if match:
            return match

    candidate_paths = _path_candidates(relative_path)
    search_systems = [system_id] if system_id else []
    search_systems.extend(target_systems)
    seen: set[str] = set()
    for candidate_system in search_systems:
        if not candidate_system or candidate_system in seen:
            continue
        seen.add(candidate_system)
        for candidate_path in candidate_paths:
            match = lookup_kg_file_node(candidate_system, candidate_path)
            if match:
                return match
    return None


def _path_candidates(relative_path: str) -> list[str]:
    normalized = relative_path.replace("\\", "/").strip()
    if not normalized:
        return []
    candidates = [normalized]
    basename = Path(normalized).name
    if basename and basename not in candidates:
        candidates.append(basename)
    return candidates


def _parse_impact_path(path_value: str, target_systems: list[str]) -> tuple[str | None, str]:
    if ":" in path_value:
        system_id, relative_path = path_value.split(":", 1)
        return system_id.strip() or None, relative_path.strip()
    if len(target_systems) == 1:
        return target_systems[0], path_value
    return None, path_value


def _read_impact_file(file_entry: Any) -> tuple[str, float | None]:
    if hasattr(file_entry, "path"):
        score = getattr(file_entry, "score", None)
        return str(file_entry.path), float(score) if score is not None else None
    if isinstance(file_entry, dict):
        score = file_entry.get("score")
        return str(file_entry.get("path", "")), float(score) if score is not None else None
    return "", None


def _overlay_label(path_value: str) -> str:
    if not path_value:
        return "System artifact"
    return Path(path_value.replace("\\", "/")).name or path_value


def _node_exists(nodes: list[GraphNode], node_id: str) -> bool:
    return any(node.id == node_id for node in nodes)

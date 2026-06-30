from typing import Any

from app.models.schemas import GraphEdge, GraphNode
from app.services.graph_builder import export_graph
import networkx as nx

EDGE_REALIZED_BY = "REALIZED_BY"
EDGE_INCLUDES_PATCH = "INCLUDES_PATCH"
EDGE_MODIFIES = "MODIFIES"
EDGE_IMPLEMENTS = "IMPLEMENTS"

IMPLEMENTATION_PLAN_TYPE = "ImplementationPlan"
CODE_CHANGE_TYPE = "CodeChange"


def extend_graph_with_implementation(
    graph_data: dict[str, Any],
    patches: list[dict[str, Any]],
    pack_id: str | None = None,
) -> dict[str, Any]:
    if not patches:
        return graph_data

    graph = nx.DiGraph()
    node_map: dict[str, GraphNode] = {}

    for raw_node in graph_data.get("nodes", []):
        if isinstance(raw_node, GraphNode):
            node = raw_node
        else:
            node = GraphNode(**raw_node)
        node_map[node.id] = node
        graph.add_node(
            node.id,
            label=node.label,
            type=node.type,
            status=node.status,
            metadata=dict(node.metadata),
        )

    for raw_edge in graph_data.get("edges", []):
        if isinstance(raw_edge, GraphEdge):
            edge = raw_edge
        else:
            edge = GraphEdge(**raw_edge)
        graph.add_edge(edge.source, edge.target, label=edge.label, type=edge.type)

    plan_id = "implementation_plan"
    plan_label = f"Implementation Plan{f' ({pack_id})' if pack_id else ''}"
    graph.add_node(
        plan_id,
        label=plan_label,
        type=IMPLEMENTATION_PLAN_TYPE,
        status="completed",
        metadata={"pack_id": pack_id, "patch_count": len(patches)},
    )

    if graph.has_node("change_contract"):
        graph.add_edge("change_contract", plan_id, label=EDGE_REALIZED_BY, type=EDGE_REALIZED_BY)

    file_nodes_by_path = _index_file_nodes(node_map)
    obligation_nodes_by_rule = _index_obligation_nodes(node_map)

    for index, patch in enumerate(patches):
        change_id = f"code_change_{index}"
        obligation = str(patch.get("obligation", ""))
        file_path = str(patch.get("file_path", ""))
        graph.add_node(
            change_id,
            label=patch.get("patch_id", change_id).replace("_", " "),
            type=CODE_CHANGE_TYPE,
            status="completed",
            metadata={
                "file_path": file_path,
                "change_type": patch.get("change_type"),
                "description": patch.get("description"),
                "lines_added": patch.get("lines_added", 0),
                "obligation": obligation,
            },
        )
        graph.add_edge(plan_id, change_id, label=EDGE_INCLUDES_PATCH, type=EDGE_INCLUDES_PATCH)

        file_node_id = _match_file_node(file_path, file_nodes_by_path)
        if file_node_id:
            graph.add_edge(change_id, file_node_id, label=EDGE_MODIFIES, type=EDGE_MODIFIES)

        obligation_node_id = _match_obligation_node(obligation, obligation_nodes_by_rule)
        if obligation_node_id:
            graph.add_edge(change_id, obligation_node_id, label=EDGE_IMPLEMENTS, type=EDGE_IMPLEMENTS)

    return export_graph(graph)


def _index_file_nodes(node_map: dict[str, GraphNode]) -> dict[str, str]:
    indexed: dict[str, str] = {}
    for node_id, node in node_map.items():
        if node.type != "File":
            continue
        path = str(node.metadata.get("path", ""))
        if path:
            indexed[path] = node_id
            indexed[path.split("/")[-1]] = node_id
    return indexed


def _index_obligation_nodes(node_map: dict[str, GraphNode]) -> dict[str, str]:
    indexed: dict[str, str] = {}
    for node_id, node in node_map.items():
        if node.type != "Obligation":
            continue
        rule = str(node.metadata.get("rule", node.label.replace(" ", "_")))
        indexed[rule] = node_id
        indexed[rule.lower()] = node_id
    return indexed


def _match_file_node(file_path: str, file_nodes_by_path: dict[str, str]) -> str | None:
    if file_path in file_nodes_by_path:
        return file_nodes_by_path[file_path]
    basename = file_path.split("/")[-1]
    return file_nodes_by_path.get(basename)


def _match_obligation_node(obligation: str, obligation_nodes_by_rule: dict[str, str]) -> str | None:
    mapping = {
        "procurement_finance_approval": "finance_approval_required",
        "supplier_confirmation_gate": "supplier_confirmation_blocked_until_approval",
        "regshift_contract_tests": "approval_event_logged",
    }
    rule = mapping.get(obligation, obligation)
    return obligation_nodes_by_rule.get(rule) or obligation_nodes_by_rule.get(rule.lower())

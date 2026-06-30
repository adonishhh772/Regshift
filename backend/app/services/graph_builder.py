from typing import Any

import networkx as nx

from app.models.schemas import GraphEdge, GraphNode


EDGE_TYPES = {
    "COMPILED_INTO": "COMPILED_INTO",
    "CONTAINS_OBLIGATION": "CONTAINS_OBLIGATION",
    "AFFECTS_PROCESS": "AFFECTS_PROCESS",
    "MAPS_TO_MODULE": "MAPS_TO_MODULE",
    "IMPLEMENTED_BY": "IMPLEMENTED_BY",
    "CONTAINS_SYMBOL": "CONTAINS_SYMBOL",
    "SUPPORTED_BY_EVIDENCE": "SUPPORTED_BY_EVIDENCE",
    "INTRODUCES_RISK": "INTRODUCES_RISK",
    "VALIDATED_BY_TEST": "VALIDATED_BY_TEST",
    "REQUIRES_APPROVAL": "REQUIRES_APPROVAL",
}


def build_graph(
    business_text: str,
    contract: dict[str, Any],
    impact: dict[str, Any],
    risks: dict[str, str],
    tests: list[dict[str, Any]],
) -> dict[str, Any]:
    graph = nx.DiGraph()
    domain = contract.get("domain", "unknown")

    _add_node(
        graph,
        "business_change",
        "Business Change",
        "BusinessChange",
        {"text": business_text[:120]},
    )
    _add_node(graph, "change_contract", "Change Contract", "ChangeContract", {"domain": domain})
    graph.add_edge("business_change", "change_contract", label="COMPILED_INTO", type="COMPILED_INTO")

    obligations = contract.get("required_behaviour", [])
    for index, obligation in enumerate(obligations):
        obligation_id = f"obligation_{index}"
        _add_node(graph, obligation_id, obligation.replace("_", " "), "Obligation", {"rule": obligation})
        graph.add_edge("change_contract", obligation_id, label="CONTAINS_OBLIGATION", type="CONTAINS_OBLIGATION")

        process_id = f"process_{index}"
        process_name = impact["processes"][index % len(impact["processes"])]
        _add_node(graph, process_id, process_name, "BusinessProcess", {})
        graph.add_edge(obligation_id, process_id, label="AFFECTS_PROCESS", type="AFFECTS_PROCESS")

        module_id = f"module_{index}"
        module_name = impact["modules"][index % len(impact["modules"])] if impact["modules"] else "erpnext"
        _add_node(graph, module_id, module_name, "ERPModule", {})
        graph.add_edge(process_id, module_id, label="MAPS_TO_MODULE", type="MAPS_TO_MODULE")

        if impact["files"]:
            file = impact["files"][index % len(impact["files"])]
            file_id = f"file_{index}"
            _add_node(
                graph,
                file_id,
                file.path.split("/")[-1],
                "File",
                {"path": file.path, "score": file.score},
            )
            graph.add_edge(module_id, file_id, label="IMPLEMENTED_BY", type="IMPLEMENTED_BY")

            if file.symbols:
                symbol_id = f"symbol_{index}"
                _add_node(graph, symbol_id, file.symbols[0], "Symbol", {})
                graph.add_edge(file_id, symbol_id, label="CONTAINS_SYMBOL", type="CONTAINS_SYMBOL")

            evidence_id = f"evidence_{index}"
            _add_node(
                graph,
                evidence_id,
                "Evidence Snippet",
                "EvidenceSnippet",
                {"snippet": file.evidence_snippet[:120]},
            )
            graph.add_edge(file_id, evidence_id, label="SUPPORTED_BY_EVIDENCE", type="SUPPORTED_BY_EVIDENCE")

        risk_name = _pick_risk(obligation, risks)
        if risk_name:
            risk_id = f"risk_{index}"
            _add_node(graph, risk_id, risk_name.replace("_", " "), "Risk", {"level": risks.get(risk_name, "medium")})
            graph.add_edge(obligation_id, risk_id, label="INTRODUCES_RISK", type="INTRODUCES_RISK")

            if tests:
                test = tests[index % len(tests)]
                test_id = f"test_{index}"
                _add_node(graph, test_id, test["name"], "Test", {"rule": test["contract_rule"]})
                graph.add_edge(risk_id, test_id, label="VALIDATED_BY_TEST", type="VALIDATED_BY_TEST")

    for role_index, role in enumerate(contract.get("approval_roles", [])):
        role_id = f"approval_{role_index}"
        _add_node(graph, role_id, role, "ApprovalRole", {})
        graph.add_edge("change_contract", role_id, label="REQUIRES_APPROVAL", type="REQUIRES_APPROVAL")

    return export_graph(graph)


def export_graph(graph: nx.DiGraph) -> dict[str, Any]:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    positions = _compute_hierarchical_layout(graph)

    for node_id, data in graph.nodes(data=True):
        position = positions.get(node_id, (0, 0))
        metadata = dict(data.get("metadata", {}))
        metadata["x"] = position[0]
        metadata["y"] = position[1]
        nodes.append(
            GraphNode(
                id=node_id,
                label=data["label"],
                type=data["type"],
                status=data.get("status", "completed"),
                metadata=metadata,
            )
        )

    for index, (source, target, data) in enumerate(graph.edges(data=True)):
        edges.append(
            GraphEdge(
                id=f"edge_{index}",
                source=source,
                target=target,
                label=data.get("label", ""),
                type=data.get("type", ""),
            )
        )

    return {"nodes": nodes, "edges": edges}


def get_trace_path(graph_data: dict[str, Any], obligation_node_id: str) -> list[str]:
    node_ids = {node.id for node in graph_data["nodes"]}
    if obligation_node_id not in node_ids:
        return []

    adjacency: dict[str, list[str]] = {}
    for edge in graph_data["edges"]:
        adjacency.setdefault(edge.source, []).append(edge.target)

    path = [obligation_node_id]
    current = obligation_node_id
    visited = {current}

    preferred_types = ["BusinessProcess", "ERPModule", "File", "SystemKGFile", "TargetSystem", "Risk", "Test", "ApprovalRole"]
    type_map = {node.id: node.type for node in graph_data["nodes"]}

    for preferred in preferred_types:
        found = False
        for neighbor in adjacency.get(current, []):
            if neighbor in visited:
                continue
            if type_map.get(neighbor) == preferred:
                path.append(neighbor)
                visited.add(neighbor)
                current = neighbor
                found = True
                break
        if not found and preferred == "ApprovalRole":
            for node in graph_data["nodes"]:
                if node.type == "ApprovalRole" and node.id not in visited:
                    path.append(node.id)
                    break

    return path


def _add_node(
    graph: nx.DiGraph,
    node_id: str,
    label: str,
    node_type: str,
    metadata: dict[str, Any],
) -> None:
    graph.add_node(node_id, label=label, type=node_type, status="completed", metadata=metadata)


def _compute_hierarchical_layout(graph: nx.DiGraph) -> dict[str, tuple[float, float]]:
    if graph.number_of_nodes() == 0:
        return {}

    roots = [node for node in graph.nodes if graph.in_degree(node) == 0]
    if not roots:
        roots = [next(iter(graph.nodes))]

    layer_by_node: dict[str, int] = {}
    queue: list[tuple[str, int]] = [(root, 0) for root in roots]
    visited: set[str] = set()

    while queue:
        node_id, depth = queue.pop(0)
        if node_id in visited:
            continue
        visited.add(node_id)
        layer_by_node[node_id] = max(layer_by_node.get(node_id, 0), depth)
        for child in graph.successors(node_id):
            queue.append((child, depth + 1))

    for node_id in graph.nodes:
        layer_by_node.setdefault(node_id, 0)

    layers: dict[int, list[str]] = {}
    for node_id, layer in layer_by_node.items():
        layers.setdefault(layer, []).append(node_id)

    positions: dict[str, tuple[float, float]] = {}
    horizontal_gap = 240
    vertical_gap = 130

    for layer_index, node_ids in sorted(layers.items()):
        sorted_nodes = sorted(node_ids)
        row_width = max(len(sorted_nodes) - 1, 0) * horizontal_gap
        start_x = -row_width / 2
        for column_index, node_id in enumerate(sorted_nodes):
            positions[node_id] = (start_x + column_index * horizontal_gap, layer_index * vertical_gap)

    return positions


def _pick_risk(obligation: str, risks: dict[str, str]) -> str | None:
    mapping = {
        "finance_approval_required": "financial_control",
        "supplier_confirmation_blocked_until_approval": "supplier_operations",
        "approval_event_logged": "audit",
        "permission_change_review_required": "permissions",
    }
    return mapping.get(obligation) or (next(iter(risks.keys())) if risks else None)

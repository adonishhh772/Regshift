from typing import Any

from app.models.schemas import GraphEdge, GraphNode
from app.services.neo4j_store import _get_driver
from app.services.policy_constants import (
    DEFAULT_TENANT_ID,
    RULE_TYPE_AGENT_LIMIT,
    RULE_TYPE_APPROVAL_ROLE,
    RULE_TYPE_OBLIGATION,
    RULE_TYPE_THRESHOLD,
)
from app.services.policy_store import get_active_policy, get_policy


def _clear_policy_document_graph(session, policy_id: str) -> None:
    session.run(
        """
        MATCH (doc:PolicyDocument {id: $policy_id})-[rel:DEFINES|GOVERNS|REQUIRES_APPROVAL|CONSTRAINS_AGENT]->(node)
        DETACH DELETE node
        """,
        policy_id=policy_id,
    )
    session.run(
        """
        MATCH (doc:PolicyDocument {id: $policy_id})-[:DEFINES]->(rule:PolicyRule)-[rel]->(node)
        DETACH DELETE node
        """,
        policy_id=policy_id,
    )


def persist_policy_knowledge_graph(
    tenant_id: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    parsed_rules = policy["rules"]
    domain = policy.get("domain") or policy["rules"].get("domain")
    if not domain:
        return {"persisted": False, "backend": "none", "reason": "missing domain"}

    driver = _get_driver()
    if driver is None:
        return {
            "persisted": False,
            "backend": "networkx_fallback",
            "node_count": _build_fallback_graph(policy).get("node_count", 0),
        }

    policy_id = policy["id"]
    rules_payload = parsed_rules if isinstance(parsed_rules, dict) else {}
    rule_items = rules_payload.get("rules", [])

    with driver.session() as session:
        _clear_policy_document_graph(session, policy_id)
        session.run(
            """
            MATCH (old:PolicyDocument {tenant_id: $tenant_id, domain: $domain, status: 'active'})
            WHERE old.id <> $policy_id
            SET old.status = 'archived'
            """,
            tenant_id=tenant_id,
            domain=domain,
            policy_id=policy_id,
        )
        session.run(
            """
            MERGE (doc:PolicyDocument {id: $policy_id})
            SET doc.tenant_id = $tenant_id,
                doc.title = $title,
                doc.domain = $domain,
                doc.version = $version,
                doc.status = 'active'
            WITH doc
            MERGE (tenant:Tenant {id: $tenant_id})
            MERGE (domain_node:Domain {name: $domain})
            MERGE (tenant)-[:OWNS]->(doc)
            MERGE (doc)-[:APPLIES_TO]->(domain_node)
            """,
            tenant_id=tenant_id,
            policy_id=policy_id,
            title=policy["title"],
            domain=domain,
            version=policy["version"],
        )

        for rule in rule_items:
            session.run(
                """
                MATCH (doc:PolicyDocument {id: $policy_id})
                MERGE (rule:PolicyRule {id: $rule_id})
                SET rule.type = $rule_type,
                    rule.value = $value,
                    rule.citation = $citation,
                    rule.description = $description,
                    rule.policy_id = $policy_id
                MERGE (doc)-[:DEFINES {citation: $citation}]->(rule)
                """,
                policy_id=policy_id,
                rule_id=rule["id"],
                rule_type=rule["type"],
                value=str(rule.get("value", rule.get("key", ""))),
                citation=rule.get("citation", "Policy document"),
                description=rule.get("description", ""),
            )

            if rule["type"] == RULE_TYPE_OBLIGATION:
                session.run(
                    """
                    MATCH (doc:PolicyDocument {id: $policy_id})-[:DEFINES]->(rule:PolicyRule {id: $rule_id})
                    MERGE (obligation:Obligation {name: $obligation_name})
                    MERGE (rule)-[:REQUIRES]->(obligation)
                    MERGE (doc)-[:GOVERNS]->(obligation)
                    """,
                    policy_id=policy_id,
                    rule_id=rule["id"],
                    obligation_name=rule["value"],
                )
            elif rule["type"] == RULE_TYPE_THRESHOLD:
                session.run(
                    """
                    MATCH (doc:PolicyDocument {id: $policy_id})-[:DEFINES]->(rule:PolicyRule {id: $rule_id})
                    MERGE (threshold:Threshold {amount: $amount, domain: $domain})
                    MERGE (rule)-[:SETS]->(threshold)
                    MERGE (doc)-[:GOVERNS]->(threshold)
                    """,
                    policy_id=policy_id,
                    rule_id=rule["id"],
                    amount=int(rule["value"]),
                    domain=domain,
                )
            elif rule["type"] == RULE_TYPE_APPROVAL_ROLE:
                session.run(
                    """
                    MATCH (doc:PolicyDocument {id: $policy_id})-[:DEFINES]->(rule:PolicyRule {id: $rule_id})
                    MERGE (role:ApprovalRole {name: $role_name})
                    MERGE (rule)-[:REQUIRES_ROLE]->(role)
                    MERGE (doc)-[:REQUIRES_APPROVAL]->(role)
                    """,
                    policy_id=policy_id,
                    rule_id=rule["id"],
                    role_name=rule["value"],
                )
            elif rule["type"] == RULE_TYPE_AGENT_LIMIT:
                session.run(
                    """
                    MATCH (doc:PolicyDocument {id: $policy_id})-[:DEFINES]->(rule:PolicyRule {id: $rule_id})
                    MERGE (limit:AgentLimit {key: $limit_key})
                    SET limit.value = $limit_value
                    MERGE (rule)-[:CONSTRAINS]->(limit)
                    MERGE (doc)-[:CONSTRAINS_AGENT]->(limit)
                    """,
                    policy_id=policy_id,
                    rule_id=rule["id"],
                    limit_key=rule["key"],
                    limit_value=str(rule["value"]),
                )

    node_count = len(rule_items) + 2
    return {
        "persisted": True,
        "backend": "neo4j",
        "policy_id": policy_id,
        "node_count": node_count,
        "edge_count": len(rule_items) * 2,
    }


def load_policy_governance_from_graph(
    domain: str,
    tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, Any] | None:
    driver = _get_driver()
    if driver is None:
        return None

    with driver.session() as session:
        doc_row = session.run(
            """
            MATCH (tenant:Tenant {id: $tenant_id})-[:OWNS]->(doc:PolicyDocument {domain: $domain, status: 'active'})
            RETURN doc.id AS policy_id, doc.title AS title, doc.version AS version
            ORDER BY doc.version DESC
            LIMIT 1
            """,
            tenant_id=tenant_id,
            domain=domain,
        ).single()

        if doc_row is None:
            return None

        policy_id = doc_row["policy_id"]
        obligations = [
            row["name"]
            for row in session.run(
                """
                MATCH (:PolicyDocument {id: $policy_id})-[:GOVERNS]->(o:Obligation)
                RETURN DISTINCT o.name AS name
                ORDER BY o.name
                """,
                policy_id=policy_id,
            ).data()
        ]
        threshold_row = session.run(
            """
            MATCH (:PolicyDocument {id: $policy_id})-[:GOVERNS]->(t:Threshold)
            RETURN t.amount AS amount
            LIMIT 1
            """,
            policy_id=policy_id,
        ).single()
        approval_roles = [
            row["name"]
            for row in session.run(
                """
                MATCH (:PolicyDocument {id: $policy_id})-[:REQUIRES_APPROVAL]->(r:ApprovalRole)
                RETURN DISTINCT r.name AS name
                ORDER BY r.name
                """,
                policy_id=policy_id,
            ).data()
        ]
        agent_limits: dict[str, bool] = {}
        for row in session.run(
            """
            MATCH (:PolicyDocument {id: $policy_id})-[:CONSTRAINS_AGENT]->(l:AgentLimit)
            RETURN l.key AS key, l.value AS value
            """,
            policy_id=policy_id,
        ).data():
            agent_limits[row["key"]] = row["value"].lower() == "true"

        citations = {
            row["value"]: row["citation"]
            for row in session.run(
                """
                MATCH (:PolicyDocument {id: $policy_id})-[:DEFINES]->(rule:PolicyRule)
                WHERE rule.type = 'obligation'
                RETURN rule.value AS value, rule.citation AS citation
                """,
                policy_id=policy_id,
            ).data()
        }
        rules = [
            {
                "id": row["id"],
                "type": row["type"],
                "value": row["value"],
                "citation": row["citation"],
                "description": row.get("description") or "",
            }
            for row in session.run(
                """
                MATCH (:PolicyDocument {id: $policy_id})-[:DEFINES]->(rule:PolicyRule)
                RETURN rule.id AS id,
                       rule.type AS type,
                       rule.value AS value,
                       rule.citation AS citation,
                       rule.description AS description
                ORDER BY rule.id
                """,
                policy_id=policy_id,
            ).data()
        ]

    return {
        "policy_id": policy_id,
        "policy_title": doc_row["title"],
        "policy_version": doc_row["version"],
        "domain": domain,
        "obligations": obligations,
        "threshold": threshold_row["amount"] if threshold_row else None,
        "approval_roles": approval_roles,
        "agent_limits": agent_limits,
        "citations": citations,
        "rules": rules,
        "source": "neo4j_policy_graph",
    }


def extract_workflow_guidance(
    domain: str,
    tenant_id: str = DEFAULT_TENANT_ID,
) -> dict[str, Any]:
    from app.services.policy_compiler import build_governance_config

    governance = build_governance_config(domain, tenant_id)
    if governance is None:
        return {
            "configured": False,
            "domain": domain,
            "required_steps": ["policy_graph_load", "contract_compile", "human_approval_gate"],
            "blocked_actions": ["pack_generate"],
            "message": "Ingest tenant policy into the knowledge graph before proceeding",
        }

    agent_limits = governance.get("agent_limits", {})
    return {
        "configured": True,
        "domain": domain,
        "policy_id": governance["policy_id"],
        "policy_title": governance["policy_title"],
        "required_obligations": governance["obligations"],
        "threshold": governance.get("threshold"),
        "approval_roles": governance.get("approval_roles", []),
        "agent_limits": agent_limits,
        "required_steps": [
            "policy_graph_load",
            "contract_compile",
            "human_approval_gate",
            "impact_analysis",
            "governance_gate",
        ],
        "blocked_actions": ["auto_merge"] if agent_limits.get("can_auto_merge") is False else [],
        "requires_human_approval": agent_limits.get("requires_human_approval", True),
        "source": governance.get("source", "policy_graph"),
    }


def get_policy_graph_visualization(
    domain: str,
    tenant_id: str = DEFAULT_TENANT_ID,
    policy_id: str | None = None,
) -> dict[str, Any]:
    policy = get_policy(policy_id) if policy_id else get_active_policy(domain, tenant_id)
    if not policy:
        return {
            "nodes": [],
            "edges": [],
            "backend": "none",
            "policy_id": None,
            "domain": domain,
            "policy_title": None,
            "policy_version": None,
        }

    resolved_domain = policy.get("domain") or domain
    resolved_policy_id = policy["id"]

    driver = _get_driver()
    if driver is not None:
        neo4j_graph = _load_graph_from_neo4j(driver, tenant_id, resolved_policy_id, resolved_domain)
        if neo4j_graph is not None:
            neo4j_graph["policy_title"] = policy.get("title")
            neo4j_graph["policy_version"] = policy.get("version")
            neo4j_graph["domain"] = resolved_domain
            return neo4j_graph

    built = _build_graph_from_policy(policy)
    built["domain"] = resolved_domain
    return built


def _load_graph_from_neo4j(
    driver: Any,
    tenant_id: str,
    policy_id: str,
    domain: str,
) -> dict[str, Any] | None:
    with driver.session() as session:
        doc_row = session.run(
            """
            MATCH (tenant:Tenant {id: $tenant_id})-[:OWNS]->(doc:PolicyDocument {id: $policy_id})
            RETURN doc.id AS id, doc.title AS title, doc.version AS version
            LIMIT 1
            """,
            tenant_id=tenant_id,
            policy_id=policy_id,
        ).single()

        if doc_row is None:
            return None

        rules = session.run(
            """
            MATCH (doc:PolicyDocument {id: $policy_id})-[:DEFINES]->(rule:PolicyRule)
            RETURN rule.id AS id, rule.type AS type, rule.value AS value,
                   rule.citation AS citation, rule.description AS description
            ORDER BY rule.id
            """,
            policy_id=policy_id,
        ).data()
        obligations = session.run(
            """
            MATCH (doc:PolicyDocument {id: $policy_id})-[:GOVERNS]->(obligation:Obligation)
            RETURN DISTINCT obligation.name AS name
            ORDER BY obligation.name
            """,
            policy_id=policy_id,
        ).data()
        thresholds = session.run(
            """
            MATCH (doc:PolicyDocument {id: $policy_id})-[:GOVERNS]->(threshold:Threshold)
            RETURN DISTINCT threshold.amount AS amount
            """,
            policy_id=policy_id,
        ).data()
        roles = session.run(
            """
            MATCH (doc:PolicyDocument {id: $policy_id})-[:REQUIRES_APPROVAL]->(role:ApprovalRole)
            RETURN DISTINCT role.name AS name
            ORDER BY role.name
            """,
            policy_id=policy_id,
        ).data()
        limits = session.run(
            """
            MATCH (doc:PolicyDocument {id: $policy_id})-[:CONSTRAINS_AGENT]->(limit:AgentLimit)
            RETURN DISTINCT limit.key AS key, limit.value AS value
            ORDER BY limit.key
            """,
            policy_id=policy_id,
        ).data()
        rule_edges = session.run(
            """
            MATCH (doc:PolicyDocument {id: $policy_id})-[:DEFINES]->(rule:PolicyRule)
            OPTIONAL MATCH (rule)-[rel]->(target)
            WHERE target:Obligation OR target:Threshold OR target:ApprovalRole OR target:AgentLimit
            RETURN rule.id AS source, target, type(rel) AS rel_type
            """,
            policy_id=policy_id,
        ).data()

    return _compose_policy_graph(
        policy_id=doc_row["id"],
        title=doc_row["title"],
        version=doc_row["version"],
        domain=domain,
        rules=rules,
        obligations=obligations,
        thresholds=thresholds,
        roles=roles,
        limits=limits,
        rule_edges=rule_edges,
        backend="neo4j",
    )


def _compose_policy_graph(
    *,
    policy_id: str,
    title: str,
    version: int,
    domain: str,
    rules: list[dict[str, Any]],
    obligations: list[dict[str, Any]],
    thresholds: list[dict[str, Any]],
    roles: list[dict[str, Any]],
    limits: list[dict[str, Any]],
    rule_edges: list[dict[str, Any]],
    backend: str,
) -> dict[str, Any]:
    nodes: list[GraphNode] = [
        GraphNode(
            id=f"policy_{policy_id}",
            label=title,
            type="PolicyDocument",
            metadata={"version": version, "domain": domain},
        )
    ]
    edges: list[GraphEdge] = []
    seen_node_ids: set[str] = {f"policy_{policy_id}"}
    edge_index = 0

    for rule in rules:
        rule_id = rule["id"]
        if rule_id in seen_node_ids:
            continue
        seen_node_ids.add(rule_id)
        nodes.append(
            GraphNode(
                id=rule_id,
                label=rule.get("description") or rule_id,
                type="PolicyRule",
                metadata={"rule_type": rule.get("type"), "citation": rule.get("citation")},
            )
        )
        edges.append(
            GraphEdge(
                id=f"policy_edge_{edge_index}",
                source=f"policy_{policy_id}",
                target=rule_id,
                label="DEFINES",
                type="DEFINES",
            )
        )
        edge_index += 1

    for row in obligations:
        obligation_name = row["name"]
        node_id = f"obligation_{obligation_name}"
        if node_id not in seen_node_ids:
            seen_node_ids.add(node_id)
            nodes.append(
                GraphNode(
                    id=node_id,
                    label=obligation_name.replace("_", " "),
                    type="Obligation",
                    metadata={"name": obligation_name},
                )
            )
        edges.append(
            GraphEdge(
                id=f"policy_edge_{edge_index}",
                source=f"policy_{policy_id}",
                target=node_id,
                label="GOVERNS",
                type="GOVERNS",
            )
        )
        edge_index += 1

    for row in thresholds:
        amount = row["amount"]
        node_id = f"threshold_{amount}"
        if node_id not in seen_node_ids:
            seen_node_ids.add(node_id)
            nodes.append(
                GraphNode(
                    id=node_id,
                    label=f"Threshold £{amount:,}",
                    type="Threshold",
                    metadata={"amount": amount},
                )
            )
        edges.append(
            GraphEdge(
                id=f"policy_edge_{edge_index}",
                source=f"policy_{policy_id}",
                target=node_id,
                label="GOVERNS",
                type="GOVERNS",
            )
        )
        edge_index += 1

    for row in roles:
        role_name = row["name"]
        node_id = f"role_{role_name.lower().replace(' ', '_')}"
        if node_id not in seen_node_ids:
            seen_node_ids.add(node_id)
            nodes.append(
                GraphNode(
                    id=node_id,
                    label=role_name,
                    type="ApprovalRole",
                    metadata={"name": role_name},
                )
            )
        edges.append(
            GraphEdge(
                id=f"policy_edge_{edge_index}",
                source=f"policy_{policy_id}",
                target=node_id,
                label="REQUIRES_APPROVAL",
                type="REQUIRES_APPROVAL",
            )
        )
        edge_index += 1

    for row in limits:
        limit_key = row["key"]
        node_id = f"limit_{limit_key}"
        if node_id not in seen_node_ids:
            seen_node_ids.add(node_id)
            nodes.append(
                GraphNode(
                    id=node_id,
                    label=f"{limit_key}={row['value']}",
                    type="AgentLimit",
                    metadata={"key": limit_key, "value": row["value"]},
                )
            )
        edges.append(
            GraphEdge(
                id=f"policy_edge_{edge_index}",
                source=f"policy_{policy_id}",
                target=node_id,
                label="CONSTRAINS_AGENT",
                type="CONSTRAINS_AGENT",
            )
        )
        edge_index += 1

    for row in rule_edges:
        target = row.get("target")
        if target is None:
            continue
        if isinstance(target, dict):
            labels = set(target.get("labels", []))
        elif hasattr(target, "labels"):
            labels = set(target.labels)
        else:
            labels = set()
        source_id = row["source"]
        if "Obligation" in labels:
            target_id = f"obligation_{target['name']}"
        elif "Threshold" in labels:
            target_id = f"threshold_{target['amount']}"
        elif "ApprovalRole" in labels:
            target_id = f"role_{target['name'].lower().replace(' ', '_')}"
        elif "AgentLimit" in labels:
            target_id = f"limit_{target['key']}"
        else:
            continue
        edges.append(
            GraphEdge(
                id=f"policy_edge_{edge_index}",
                source=source_id,
                target=target_id,
                label=str(row.get("rel_type", "LINKS")),
                type=str(row.get("rel_type", "LINKS")),
            )
        )
        edge_index += 1

    unique_edges: list[GraphEdge] = []
    seen_edge_keys: set[tuple[str, str, str]] = set()
    for edge in edges:
        edge_key = (edge.source, edge.target, edge.label)
        if edge_key in seen_edge_keys:
            continue
        seen_edge_keys.add(edge_key)
        unique_edges.append(edge)

    return {
        "nodes": [node.model_dump() for node in nodes],
        "edges": [edge.model_dump() for edge in unique_edges],
        "backend": backend,
        "policy_id": policy_id,
        "policy_title": title,
        "policy_version": version,
        "domain": domain,
    }


def _build_graph_from_policy(policy: dict[str, Any]) -> dict[str, Any]:
    if not policy:
        return {
            "nodes": [],
            "edges": [],
            "backend": "networkx_fallback",
            "node_count": 0,
            "policy_id": None,
            "policy_title": None,
            "policy_version": None,
            "domain": None,
        }

    rules_payload = policy.get("rules", {})
    rule_items = rules_payload.get("rules", []) if isinstance(rules_payload, dict) else []
    policy_id = policy.get("id", "unknown")
    domain = policy.get("domain") or rules_payload.get("domain") or "unknown"

    obligations = [
        {"name": rule["value"]}
        for rule in rule_items
        if rule.get("type") == RULE_TYPE_OBLIGATION and rule.get("value")
    ]
    thresholds = [
        {"amount": int(rule["value"])}
        for rule in rule_items
        if rule.get("type") == RULE_TYPE_THRESHOLD and rule.get("value") is not None
    ]
    roles = [
        {"name": rule["value"]}
        for rule in rule_items
        if rule.get("type") == RULE_TYPE_APPROVAL_ROLE and rule.get("value")
    ]
    limits = [
        {"key": rule["key"], "value": str(rule["value"])}
        for rule in rule_items
        if rule.get("type") == RULE_TYPE_AGENT_LIMIT and rule.get("key")
    ]
    rule_edges: list[dict[str, Any]] = []

    for rule in rule_items:
        rule_type = rule.get("type")
        if rule_type == RULE_TYPE_OBLIGATION:
            rule_edges.append(
                {
                    "source": rule["id"],
                    "target": {"name": rule["value"], "labels": ["Obligation"]},
                    "rel_type": "REQUIRES",
                }
            )
        elif rule_type == RULE_TYPE_THRESHOLD:
            rule_edges.append(
                {
                    "source": rule["id"],
                    "target": {"amount": int(rule["value"]), "labels": ["Threshold"]},
                    "rel_type": "SETS",
                }
            )
        elif rule_type == RULE_TYPE_APPROVAL_ROLE:
            rule_edges.append(
                {
                    "source": rule["id"],
                    "target": {"name": rule["value"], "labels": ["ApprovalRole"]},
                    "rel_type": "REQUIRES_ROLE",
                }
            )
        elif rule_type == RULE_TYPE_AGENT_LIMIT:
            rule_edges.append(
                {
                    "source": rule["id"],
                    "target": {"key": rule["key"], "value": str(rule["value"]), "labels": ["AgentLimit"]},
                    "rel_type": "CONSTRAINS",
                }
            )

    graph = _compose_policy_graph(
        policy_id=policy_id,
        title=policy.get("title", "Policy"),
        version=int(policy.get("version", 1)),
        domain=domain,
        rules=rule_items,
        obligations=obligations,
        thresholds=thresholds,
        roles=roles,
        limits=limits,
        rule_edges=rule_edges,
        backend="networkx_fallback",
    )
    graph["node_count"] = len(graph["nodes"])
    return graph


def _build_fallback_graph(policy: dict[str, Any]) -> dict[str, Any]:
    return _build_graph_from_policy(policy)

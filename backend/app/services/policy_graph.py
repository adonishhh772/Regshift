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
from app.services.policy_store import get_active_policy


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
        session.run(
            """
            MATCH (old:PolicyDocument {tenant_id: $tenant_id, domain: $domain, status: 'active'})
            SET old.status = 'archived'
            """,
            tenant_id=tenant_id,
            domain=domain,
        )
        session.run(
            """
            MERGE (tenant:Tenant {id: $tenant_id})
            MERGE (domain_node:Domain {name: $domain})
            CREATE (doc:PolicyDocument {
                id: $policy_id,
                tenant_id: $tenant_id,
                title: $title,
                domain: $domain,
                version: $version,
                status: 'active'
            })
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
                CREATE (rule:PolicyRule {
                    id: $rule_id,
                    type: $rule_type,
                    value: $value,
                    citation: $citation,
                    description: $description
                })
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
                RETURN o.name AS name
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
                RETURN r.name AS name
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
) -> dict[str, Any]:
    driver = _get_driver()
    if driver is None:
        return _build_fallback_graph(get_active_policy(domain, tenant_id) or {})

    with driver.session() as session:
        doc_row = session.run(
            """
            MATCH (tenant:Tenant {id: $tenant_id})-[:OWNS]->(doc:PolicyDocument {domain: $domain, status: 'active'})
            RETURN doc.id AS id, doc.title AS title, doc.version AS version
            ORDER BY doc.version DESC
            LIMIT 1
            """,
            tenant_id=tenant_id,
            domain=domain,
        ).single()

        if doc_row is None:
            return _build_fallback_graph(get_active_policy(domain, tenant_id) or {})

        policy_id = doc_row["id"]
        node_rows = session.run(
            """
            MATCH (doc:PolicyDocument {id: $policy_id})
            OPTIONAL MATCH (doc)-[:DEFINES]->(rule:PolicyRule)
            OPTIONAL MATCH (doc)-[:GOVERNS]->(obligation:Obligation)
            OPTIONAL MATCH (doc)-[:GOVERNS]->(threshold:Threshold)
            OPTIONAL MATCH (doc)-[:REQUIRES_APPROVAL]->(role:ApprovalRole)
            OPTIONAL MATCH (doc)-[:CONSTRAINS_AGENT]->(limit:AgentLimit)
            RETURN
                doc.id AS doc_id,
                doc.title AS doc_title,
                collect(DISTINCT rule) AS rules,
                collect(DISTINCT obligation) AS obligations,
                collect(DISTINCT threshold) AS thresholds,
                collect(DISTINCT role) AS roles,
                collect(DISTINCT limit) AS limits
            """,
            policy_id=policy_id,
        ).single()

    nodes: list[GraphNode] = [
        GraphNode(
            id=f"policy_{policy_id}",
            label=doc_row["title"],
            type="PolicyDocument",
            metadata={"version": doc_row["version"], "domain": domain},
        )
    ]
    edges: list[GraphEdge] = []
    edge_index = 0

    if node_rows:
        for rule in node_rows["rules"] or []:
            if rule is None:
                continue
            rule_id = rule.get("id")
            nodes.append(
                GraphNode(
                    id=rule_id,
                    label=rule.get("description", rule_id),
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

        for obligation in node_rows["obligations"] or []:
            if obligation is None:
                continue
            node_id = f"obligation_{obligation['name']}"
            nodes.append(
                GraphNode(
                    id=node_id,
                    label=obligation["name"].replace("_", " "),
                    type="Obligation",
                    metadata={"name": obligation["name"]},
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

    return {
        "nodes": [node.model_dump() for node in nodes],
        "edges": [edge.model_dump() for edge in edges],
        "backend": "neo4j",
        "policy_id": policy_id,
    }


def _build_fallback_graph(policy: dict[str, Any]) -> dict[str, Any]:
    if not policy:
        return {"nodes": [], "edges": [], "backend": "networkx_fallback", "node_count": 0}

    rules_payload = policy.get("rules", {})
    rule_items = rules_payload.get("rules", []) if isinstance(rules_payload, dict) else []
    policy_id = policy.get("id", "unknown")
    nodes = [
        {
            "id": f"policy_{policy_id}",
            "label": policy.get("title", "Policy"),
            "type": "PolicyDocument",
            "status": "completed",
            "metadata": {"domain": policy.get("domain"), "version": policy.get("version")},
        }
    ]
    edges = []
    for index, rule in enumerate(rule_items):
        nodes.append(
            {
                "id": rule["id"],
                "label": rule.get("description", rule["id"]),
                "type": "PolicyRule",
                "status": "completed",
                "metadata": {"rule_type": rule["type"], "citation": rule.get("citation")},
            }
        )
        edges.append(
            {
                "id": f"policy_edge_{index}",
                "source": f"policy_{policy_id}",
                "target": rule["id"],
                "label": "DEFINES",
                "type": "DEFINES",
            }
        )
    return {
        "nodes": nodes,
        "edges": edges,
        "backend": "networkx_fallback",
        "node_count": len(nodes),
    }

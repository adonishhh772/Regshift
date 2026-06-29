from typing import Any

from app.services.domain_loader import load_domain_pack
from app.services.policy_constants import (
    DEFAULT_AGENT_LIMITS,
    RULE_TYPE_AGENT_LIMIT,
    RULE_TYPE_APPROVAL_ROLE,
    RULE_TYPE_OBLIGATION,
    RULE_TYPE_THRESHOLD,
)
from app.services.policy_store import get_active_policy


def parse_policy_record_to_governance(policy: dict[str, Any], domain: str) -> dict[str, Any]:
    rules_payload = policy["rules"]
    rule_items = rules_payload.get("rules", []) if isinstance(rules_payload, dict) else rules_payload
    obligations = [
        rule["value"]
        for rule in rule_items
        if rule["type"] == RULE_TYPE_OBLIGATION
    ]
    if not obligations and isinstance(rules_payload, dict):
        obligations = list(rules_payload.get("obligations", []))

    threshold_rules = [rule for rule in rule_items if rule["type"] == RULE_TYPE_THRESHOLD]
    approval_roles = [
        rule["value"]
        for rule in rule_items
        if rule["type"] == RULE_TYPE_APPROVAL_ROLE
    ]
    if not approval_roles and isinstance(rules_payload, dict):
        approval_roles = list(rules_payload.get("approval_roles", []))

    agent_limits = dict(DEFAULT_AGENT_LIMITS)
    for rule in rule_items:
        if rule["type"] == RULE_TYPE_AGENT_LIMIT:
            agent_limits[rule["key"]] = rule["value"]
    if isinstance(rules_payload, dict) and rules_payload.get("agent_limits"):
        agent_limits.update(rules_payload["agent_limits"])

    threshold = threshold_rules[0]["value"] if threshold_rules else rules_payload.get("threshold")
    citations = {
        rule["value"] if rule["type"] != RULE_TYPE_AGENT_LIMIT else rule["key"]: rule["citation"]
        for rule in rule_items
        if rule["type"] == RULE_TYPE_OBLIGATION
    }

    return {
        "policy_id": policy["id"],
        "policy_title": policy["title"],
        "policy_version": policy["version"],
        "domain": domain,
        "obligations": obligations,
        "threshold": threshold,
        "approval_roles": approval_roles,
        "agent_limits": agent_limits,
        "citations": citations,
        "rules": rule_items,
        "source": "sqlite_policy_store",
    }


def build_governance_config(domain: str, tenant_id: str | None = None) -> dict[str, Any] | None:
    from app.services.policy_constants import DEFAULT_TENANT_ID
    from app.services.policy_graph import load_policy_governance_from_graph

    resolved_tenant = tenant_id or DEFAULT_TENANT_ID
    graph_config = load_policy_governance_from_graph(domain, resolved_tenant)
    if graph_config is not None:
        return graph_config

    policy = get_active_policy(domain, resolved_tenant)
    if policy is None:
        return None

    return parse_policy_record_to_governance(policy, domain)


def merge_policy_into_contract(
    contract: dict[str, Any],
    domain: str,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    governance = build_governance_config(domain, tenant_id)
    if governance is None:
        return contract

    merged = dict(contract)
    pack = load_domain_pack(domain)

    policy_obligations = governance["obligations"]
    contract_obligations = list(merged.get("required_behaviour", []))
    merged["required_behaviour"] = list(dict.fromkeys(policy_obligations + contract_obligations))

    if governance["threshold"] is not None:
        merged["trigger"] = {"condition": f"total_amount > {governance['threshold']}"}
        merged["policy_threshold"] = governance["threshold"]

    if governance["approval_roles"]:
        merged["approval_roles"] = governance["approval_roles"]
    elif not merged.get("approval_roles"):
        merged["approval_roles"] = pack.get("approval_roles", [])

    merged["agent_limits"] = governance["agent_limits"]
    merged["policy_citations"] = _build_policy_citations(merged["required_behaviour"], governance)
    merged["policy_source"] = {
        "policy_id": governance["policy_id"],
        "title": governance["policy_title"],
        "version": governance["policy_version"],
    }

    merged["risks"] = _merge_risks(merged["required_behaviour"], merged.get("risks", {}), pack)
    return merged


def evaluate_contract_policy_compliance(
    contract: dict[str, Any],
    domain: str,
    tenant_id: str | None = None,
) -> list[dict[str, Any]]:
    governance = build_governance_config(domain, tenant_id)
    if governance is None:
        return []

    checks: list[dict[str, Any]] = []
    contract_obligations = set(contract.get("required_behaviour", []))
    policy_obligations = set(governance["obligations"])

    missing_obligations = policy_obligations - contract_obligations
    checks.append(
        {
            "id": "contract_obligations_policy_compliant",
            "name": "Contract obligations match tenant policy",
            "passed": len(missing_obligations) == 0,
            "severity": "critical",
            "explanation": (
                "All policy-required obligations are present in the Change Contract"
                if not missing_obligations
                else f"Missing policy obligations: {', '.join(sorted(missing_obligations))}"
            ),
        }
    )

    policy_threshold = governance["threshold"]
    if policy_threshold is not None:
        contract_threshold = _extract_contract_threshold(contract)
        threshold_aligned = contract_threshold is not None and contract_threshold >= policy_threshold
        checks.append(
            {
                "id": "threshold_within_policy_bounds",
                "name": "Threshold aligned with tenant policy",
                "passed": threshold_aligned,
                "severity": "high",
                "explanation": (
                    f"Contract threshold £{contract_threshold:,} meets policy minimum £{policy_threshold:,}"
                    if threshold_aligned
                    else f"Contract threshold must be at least £{policy_threshold:,} per tenant policy"
                ),
            }
        )

    policy_roles = set(governance["approval_roles"])
    contract_roles = set(contract.get("approval_roles", []))
    roles_matched = policy_roles.issubset(contract_roles) if policy_roles else True
    checks.append(
        {
            "id": "approval_roles_match_policy",
            "name": "Approval roles match tenant policy",
            "passed": roles_matched,
            "severity": "high",
            "explanation": (
                "All policy-required approval roles are assigned"
                if roles_matched
                else f"Missing approval roles: {', '.join(sorted(policy_roles - contract_roles))}"
            ),
        }
    )

    citations = contract.get("policy_citations", {})
    citations_present = len(citations) >= 1
    checks.append(
        {
            "id": "policy_citations_present",
            "name": "Policy citations linked to contract",
            "passed": citations_present,
            "severity": "medium",
            "explanation": (
                f"{len(citations)} obligation(s) cite tenant policy clauses"
                if citations_present
                else "Change Contract must cite tenant policy clauses for audit traceability"
            ),
        }
    )

    agent_limits = governance["agent_limits"]
    contract_limits = contract.get("agent_limits", {})
    auto_merge_blocked = contract_limits.get("can_auto_merge", True) is False
    policy_blocks_auto_merge = agent_limits.get("can_auto_merge") is False
    checks.append(
        {
            "id": "agent_limits_policy_derived",
            "name": "Agent limits derived from tenant policy",
            "passed": auto_merge_blocked if policy_blocks_auto_merge else True,
            "severity": "critical",
            "explanation": (
                "Agent auto-merge blocked per tenant policy"
                if auto_merge_blocked
                else "Tenant policy requires blocking autonomous merge"
            ),
        }
    )

    return checks


def _build_policy_citations(
    obligations: list[str],
    governance: dict[str, Any],
) -> dict[str, str]:
    citations: dict[str, str] = {}
    for rule in governance["rules"]:
        if rule["type"] != RULE_TYPE_OBLIGATION:
            continue
        if rule["value"] in obligations:
            citations[rule["value"]] = rule["citation"]
    return citations


def _merge_risks(
    obligations: list[str],
    existing_risks: dict[str, str],
    pack: dict[str, Any],
) -> dict[str, str]:
    risks = dict(existing_risks) if existing_risks else {
        "financial_control": "medium",
        "supplier_operations": "medium",
        "permissions": "medium",
        "audit": "medium",
        "regression": "medium",
    }
    if "finance_approval_required" in obligations:
        risks["financial_control"] = "high"
    if "supplier_confirmation_blocked_until_approval" in obligations:
        risks["supplier_operations"] = "medium"
    if "approval_event_logged" in obligations:
        risks["audit"] = "high"
    if any("approval" in item for item in obligations):
        risks["permissions"] = "high"

    for rule in pack.get("risk_rules", []):
        if "financial_control high" in rule and "finance" in " ".join(obligations):
            risks["financial_control"] = "high"
        if "permission high" in rule and "approval" in " ".join(obligations):
            risks["permissions"] = "high"
        if "audit high" in rule and "log" in " ".join(obligations):
            risks["audit"] = "high"
    return risks


def _extract_contract_threshold(contract: dict[str, Any]) -> int | None:
    if "policy_threshold" in contract:
        return int(contract["policy_threshold"])
    trigger = contract.get("trigger", {})
    condition = trigger.get("condition", "")
    if ">" in condition:
        try:
            return int(condition.split(">")[-1].strip())
        except ValueError:
            return None
    return None

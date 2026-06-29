from typing import Any

from app.services.domain_loader import load_domain_pack
from app.services.policy_compiler import build_governance_config

BLOCKED_MESSAGE = (
    "Agent blocked from autonomous change because this touches "
    "financial control, permissions, and audit evidence."
)


def score_risks(
    contract: dict[str, Any],
    impact: dict[str, Any],
    domain: str,
) -> dict[str, Any]:
    pack = load_domain_pack(domain)
    governance = build_governance_config(domain)
    contract_risks = dict(contract.get("risks", {}))
    obligations = contract.get("required_behaviour", [])

    if "finance_approval_required" in obligations:
        contract_risks["financial_control"] = "high"
    if "supplier_confirmation_blocked_until_approval" in obligations:
        contract_risks["supplier_operations"] = "medium"
    if "approval_event_logged" in obligations:
        contract_risks["audit"] = "high"
    if any("approval" in item for item in obligations):
        contract_risks["permissions"] = "high"

    file_paths = " ".join(file.path.lower() for file in impact.get("files", []))
    if any(keyword in file_paths for keyword in ["submit", "validate", "workflow"]):
        contract_risks["regression"] = "high"
    elif impact.get("files"):
        contract_risks["regression"] = contract_risks.get("regression", "medium")

    agent_limits = dict(governance["agent_limits"]) if governance else dict(pack.get("agent_limits", {}))
    if contract.get("agent_limits"):
        agent_limits = {**agent_limits, **contract["agent_limits"]}
    agent_limits.setdefault("can_generate_tests", True)
    agent_limits.setdefault("can_generate_patch", True)
    agent_limits.setdefault("can_auto_merge", False)
    agent_limits.setdefault("requires_human_approval", True)

    high_risk_count = sum(1 for level in contract_risks.values() if level == "high")
    autonomous_allowed = high_risk_count == 0 and not agent_limits.get("requires_human_approval", True)

    blocked_message = BLOCKED_MESSAGE
    if governance:
        blocked_message = (
            f"Agent constrained by tenant policy '{governance['policy_title']}' (v{governance['policy_version']}). "
            "Human approval required before merge."
        )
    elif high_risk_count == 0:
        blocked_message = "Agent may propose changes but human approval is still required before merge."

    return {
        "risks": contract_risks,
        "agent_limits": agent_limits,
        "blocked_message": blocked_message,
        "autonomous_change_allowed": autonomous_allowed,
        "policy_source": contract.get("policy_source"),
    }

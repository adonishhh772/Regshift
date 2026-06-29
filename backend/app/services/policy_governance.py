from typing import Any

from app.models.schemas import GovernanceCheck, GovernanceEvaluation
from app.services.domain_loader import load_domain_pack
from app.services.policy_compiler import evaluate_contract_policy_compliance
from app.services.policy_store import has_active_policy


def evaluate_production_gate(session: dict[str, Any]) -> GovernanceEvaluation:
    contract = session.get("contract") or {}
    if isinstance(session.get("contract_json"), str):
        import json

        contract = json.loads(session["contract_json"])

    risks = session.get("risks") or {}
    if isinstance(session.get("risks_json"), str):
        import json

        risks = json.loads(session["risks_json"])

    tests = session.get("tests") or []
    if isinstance(session.get("tests_json"), str):
        import json

        tests = json.loads(session["tests_json"])

    simulation = session.get("simulation") or {}
    if isinstance(session.get("simulation_json"), str):
        import json

        simulation = json.loads(session["simulation_json"])

    graph = session.get("graph") or {}
    if isinstance(session.get("graph_json"), str):
        import json

        graph = json.loads(session["graph_json"])

    domain = session.get("domain", contract.get("domain", "procurement"))
    pack = load_domain_pack(domain)
    contract_agent_limits = contract.get("agent_limits", {})
    agent_limits = risks.get("agent_limits", contract_agent_limits or pack.get("agent_limits", {}))

    after_cases = simulation.get("after", [])
    simulation_passed = all(case.get("verdict") == "pass" for case in after_cases) if after_cases else False

    checks: list[GovernanceCheck] = [
        GovernanceCheck(
            id="contract_human_approved",
            name="Change Contract human-approved",
            passed=bool(session.get("contract_approved")),
            severity="critical",
            explanation="Production changes require explicit human approval of the Change Contract",
        ),
        GovernanceCheck(
            id="obligations_defined",
            name="Contract obligations defined",
            passed=len(contract.get("required_behaviour", [])) >= 1,
            severity="critical",
            explanation="At least one machine-checkable obligation must exist",
        ),
        GovernanceCheck(
            id="impact_evidence_present",
            name="Impact evidence indexed",
            passed=_impact_file_count(session) >= 3,
            severity="high",
            explanation="Impact analysis must identify at least 3 evidence-backed files",
        ),
        GovernanceCheck(
            id="graph_traceable",
            name="Knowledge graph traceable",
            passed=len(graph.get("nodes", [])) >= 8,
            severity="high",
            explanation="Graph must connect business intent to modules, files, risks, and tests",
        ),
        GovernanceCheck(
            id="risk_assessment_complete",
            name="Risk assessment complete",
            passed=bool(risks.get("risks")),
            severity="high",
            explanation="Financial, permission, and audit risks must be scored",
        ),
        GovernanceCheck(
            id="agent_auto_merge_blocked",
            name="Autonomous merge blocked",
            passed=agent_limits.get("can_auto_merge") is False,
            severity="critical",
            explanation="Agent must not auto-merge changes touching financial control or permissions",
        ),
        GovernanceCheck(
            id="tests_linked_to_contract",
            name="Tests linked to contract",
            passed=len(tests) >= 5,
            severity="high",
            explanation="Minimum 5 contract-linked regression tests required",
        ),
        GovernanceCheck(
            id="simulation_after_passes",
            name="After-change simulation passes",
            passed=simulation_passed,
            severity="critical",
            explanation="All after-change behavioural cases must pass before production gate opens",
        ),
        GovernanceCheck(
            id="approval_roles_assigned",
            name="Approval roles assigned",
            passed=len(contract.get("approval_roles", [])) >= 2,
            severity="medium",
            explanation="Finance and engineering sign-off roles must be defined",
        ),
    ]

    policy_active = has_active_policy(domain)
    checks.insert(
        0,
        GovernanceCheck(
            id="tenant_policy_active",
            name="Tenant policy corpus active",
            passed=policy_active,
            severity="high",
            explanation=(
                "Active tenant policy governs this domain"
                if policy_active
                else "No tenant policy ingested for this domain — ingest business policy before production changes"
            ),
        ),
    )

    policy_checks = evaluate_contract_policy_compliance(contract, domain)
    for policy_check in policy_checks:
        checks.append(
            GovernanceCheck(
                id=policy_check["id"],
                name=policy_check["name"],
                passed=policy_check["passed"],
                severity=policy_check["severity"],
                explanation=policy_check["explanation"],
            )
        )

    failed_critical = [check for check in checks if not check.passed and check.severity == "critical"]
    failed_any = [check for check in checks if not check.passed]
    passed = len(failed_critical) == 0 and len(failed_any) == 0

    if failed_critical:
        gate_status = "blocked"
        summary = f"Production gate BLOCKED — {len(failed_critical)} critical policy violation(s)"
    elif failed_any:
        gate_status = "conditional"
        summary = f"Production gate CONDITIONAL — {len(failed_any)} policy check(s) require attention"
    else:
        gate_status = "open"
        summary = "Production gate OPEN — all policy governance checks passed"

    return GovernanceEvaluation(
        gate_status=gate_status,
        passed=passed,
        checks=checks,
        summary=summary,
        agent_limits=agent_limits,
        blocked_message=risks.get("blocked_message", ""),
        evaluation_trace_id=f"gov-{session.get('id', 'unknown')}",
    )


def _impact_file_count(session: dict[str, Any]) -> int:
    impact = session.get("impact") or {}
    if isinstance(session.get("impact_json"), str):
        import json

        impact = json.loads(session["impact_json"])
    return len(impact.get("files", []))

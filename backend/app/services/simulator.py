from dataclasses import dataclass
from typing import Any

from app.models.schemas import SimulationCase

OBLIGATION_FINANCE_APPROVAL = "finance_approval_required"
OBLIGATION_SUPPLIER_BLOCKED = "supplier_confirmation_blocked_until_approval"
OBLIGATION_APPROVAL_LOGGED = "approval_event_logged"

DOMAIN_DEFAULT_THRESHOLDS: dict[str, int] = {
    "procurement": 25000,
    "inventory": 10000,
    "hr_compliance": 48,
    "finance_billing": 5000,
    "security": 0,
}

APPROVAL_KEYWORDS = ("approval", "approve", "sign_off", "signoff", "review")


@dataclass(frozen=True)
class ScenarioSpec:
    label: str
    amount: float
    approval: str
    before_result: str
    before_verdict: str
    after_result: str
    after_verdict: str
    contract_rules: tuple[str, ...]


def run_simulation(contract: dict[str, Any], domain: str) -> dict[str, Any]:
    threshold = _get_threshold(contract, domain)
    entity = contract.get("entity", "transaction")
    obligations = list(contract.get("required_behaviour", []))
    approval_roles = list(contract.get("approval_roles", []))
    exceptions = list(contract.get("exceptions", []))

    specs = _derive_scenario_specs(
        contract=contract,
        domain=domain,
        threshold=threshold,
        entity=entity,
        obligations=obligations,
        approval_roles=approval_roles,
        exceptions=exceptions,
    )

    before = [
        SimulationCase(
            label=spec.label,
            amount=spec.amount,
            approval=spec.approval,
            result=spec.before_result,
            verdict=spec.before_verdict,
        )
        for spec in specs
    ]
    after = [
        SimulationCase(
            label=spec.label,
            amount=spec.amount,
            approval=spec.approval,
            result=spec.after_result,
            verdict=spec.after_verdict,
        )
        for spec in specs
    ]

    summary = _build_summary(
        entity=entity,
        threshold=threshold,
        domain=domain,
        obligations=obligations,
        scenario_count=len(specs),
    )

    return {
        "before": before,
        "after": after,
        "summary": summary,
        "contract_driven": True,
        "scenario_rules": [list(spec.contract_rules) for spec in specs],
    }


def _derive_scenario_specs(
    contract: dict[str, Any],
    domain: str,
    threshold: int,
    entity: str,
    obligations: list[str],
    approval_roles: list[str],
    exceptions: list[str],
) -> list[ScenarioSpec]:
    entity_label = entity.replace("_", " ").title()
    metric = _metric_label(domain)
    under_amount = _under_threshold_amount(threshold, domain)
    over_amount = _over_threshold_amount(threshold, domain)
    primary_approver = _primary_approver_slug(approval_roles)
    requires_approval = _requires_approval_gate(obligations)

    specs: list[ScenarioSpec] = []

    exception_rule = exceptions[0] if exceptions else "exceptions"
    specs.append(
        ScenarioSpec(
            label=f"{entity_label} under {metric} threshold ({under_amount:,.0f})",
            amount=float(under_amount),
            approval="none",
            before_result="allowed",
            before_verdict="pass",
            after_result="allowed",
            after_verdict="pass",
            contract_rules=(exception_rule, contract.get("trigger", {}).get("condition", "threshold")),
        )
    )

    if requires_approval or threshold > 0:
        specs.append(
            ScenarioSpec(
                label=f"{entity_label} over threshold ({over_amount:,.0f}), no approval",
                amount=float(over_amount),
                approval="none",
                before_result="allowed",
                before_verdict="policy violation",
                after_result="blocked",
                after_verdict="pass",
                contract_rules=_matching_obligations(
                    obligations,
                    (OBLIGATION_FINANCE_APPROVAL, "approval"),
                ),
            )
        )
        specs.append(
            ScenarioSpec(
                label=f"{entity_label} over threshold ({over_amount:,.0f}), {primary_approver} approved",
                amount=float(over_amount),
                approval=primary_approver,
                before_result="allowed",
                before_verdict="pass",
                after_result="allowed",
                after_verdict="pass",
                contract_rules=_matching_obligations(
                    obligations,
                    (OBLIGATION_FINANCE_APPROVAL, "approval"),
                ),
            )
        )

    if OBLIGATION_SUPPLIER_BLOCKED in obligations:
        specs.append(
            ScenarioSpec(
                label=f"Supplier confirmation on {entity_label} before finance approval",
                amount=float(over_amount),
                approval="none",
                before_result="allowed",
                before_verdict="policy violation",
                after_result="blocked",
                after_verdict="pass",
                contract_rules=(OBLIGATION_SUPPLIER_BLOCKED,),
            )
        )

    if OBLIGATION_APPROVAL_LOGGED in obligations:
        specs.append(
            ScenarioSpec(
                label=f"Approval event audit trail for {entity_label}",
                amount=float(over_amount),
                approval=primary_approver,
                before_result="allowed",
                before_verdict="policy violation",
                after_result="allowed",
                after_verdict="pass",
                contract_rules=(OBLIGATION_APPROVAL_LOGGED,),
            )
        )

    if approval_roles:
        specs.append(
            ScenarioSpec(
                label=f"Unauthorized role cannot approve {entity_label}",
                amount=float(over_amount),
                approval="unauthorized_user",
                before_result="allowed",
                before_verdict="policy violation",
                after_result="blocked",
                after_verdict="pass",
                contract_rules=tuple(approval_roles[:1]) if approval_roles else ("permissions",),
            )
        )

    for obligation in obligations:
        if obligation in {
            OBLIGATION_FINANCE_APPROVAL,
            OBLIGATION_SUPPLIER_BLOCKED,
            OBLIGATION_APPROVAL_LOGGED,
        }:
            continue
        if any(keyword in obligation for keyword in APPROVAL_KEYWORDS):
            continue
        specs.append(
            ScenarioSpec(
                label=f"Obligation: {obligation.replace('_', ' ')}",
                amount=float(over_amount),
                approval=primary_approver if requires_approval else "none",
                before_result="allowed",
                before_verdict="policy violation",
                after_result="blocked",
                after_verdict="pass",
                contract_rules=(obligation,),
            )
        )

    required_tests = contract.get("required_tests", [])
    for index, test_description in enumerate(required_tests[:2]):
        specs.append(
            ScenarioSpec(
                label=f"Contract test: {test_description[:80]}",
                amount=float(over_amount if index % 2 == 0 else under_amount),
                approval=primary_approver if index % 2 == 0 and requires_approval else "none",
                before_result="allowed",
                before_verdict="policy violation" if index % 2 == 0 else "pass",
                after_result="blocked" if index % 2 == 0 else "allowed",
                after_verdict="pass",
                contract_rules=(f"required_tests[{index}]",),
            )
        )

    return specs


def _get_threshold(contract: dict[str, Any], domain: str) -> int:
    condition = contract.get("trigger", {}).get("condition", "")
    if ">" in condition:
        raw_value = condition.split(">")[-1].strip()
        digits = "".join(character for character in raw_value if character.isdigit())
        if digits:
            return int(digits)
    return DOMAIN_DEFAULT_THRESHOLDS.get(domain, 25000)


def _under_threshold_amount(threshold: int, domain: str) -> int:
    if domain == "hr_compliance":
        return max(1, threshold - 8)
    if threshold <= 0:
        return 0
    return max(1, int(threshold * 0.8))


def _over_threshold_amount(threshold: int, domain: str) -> int:
    if domain == "hr_compliance":
        return threshold + 12
    if threshold <= 0:
        return 1000
    return int(threshold * 1.2)


def _metric_label(domain: str) -> str:
    if domain == "hr_compliance":
        return "hour"
    return "amount"


def _primary_approver_slug(approval_roles: list[str]) -> str:
    if not approval_roles:
        return "finance"
    role = approval_roles[0].lower()
    return role.replace(" ", "_").replace("-", "_")


def _requires_approval_gate(obligations: list[str]) -> bool:
    if OBLIGATION_FINANCE_APPROVAL in obligations:
        return True
    return any(any(keyword in obligation for keyword in APPROVAL_KEYWORDS) for obligation in obligations)


def _matching_obligations(obligations: list[str], keywords: tuple[str, ...]) -> tuple[str, ...]:
    matched = [
        obligation
        for obligation in obligations
        if any(keyword in obligation for keyword in keywords)
    ]
    return tuple(matched) if matched else ("required_behaviour",)


def _build_summary(
    entity: str,
    threshold: int,
    domain: str,
    obligations: list[str],
    scenario_count: int,
) -> str:
    entity_label = entity.replace("_", " ")
    metric = _metric_label(domain)
    obligation_summary = ", ".join(obligations[:4]) if obligations else "contract obligations"
    if len(obligations) > 4:
        obligation_summary += f" (+{len(obligations) - 4} more)"
    return (
        f"Generated {scenario_count} scenarios from Change Contract for {entity_label}. "
        f"Threshold: {threshold:,} ({metric}). "
        f"Before change: high-value flows may bypass {obligation_summary}. "
        f"After change: contract rules enforce approval gates and audit controls."
    )

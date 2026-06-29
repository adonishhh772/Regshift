from typing import TypedDict


class WorkflowState(TypedDict, total=False):
    session_id: str
    business_text: str
    domain: str
    contract_yaml: str
    contract_approved: bool
    current_step: str
    index_scanned: bool
    impact_analyzed: bool
    graph_persisted: bool
    risks_scored: bool
    tests_generated: bool
    simulation_run: bool
    governance_passed: bool
    pack_generated: bool
    gate_status: str
    blocked_reason: str | None
    policy_guidance: dict[str, object] | None

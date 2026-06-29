from typing import Any

from app.orchestration.workflow import STEP_ORDER, get_workflow_status
from app.services.langfuse_tracer import ALL_WORKFLOW_STEPS, build_session_trace_url, langfuse_status


STEP_TO_API_ACTION: dict[str, str] = {
    "intake": "classify_change",
    "policy_graph_load": "classify_change",
    "classify_change": "classify_change",
    "contract_compile": "contract_generate",
    "human_approval_gate": "contract_approve",
    "index_scan": "impact_analyze",
    "impact_analysis": "impact_analyze",
    "graph_persist": "impact_analyze",
    "risk_scoring": "risk_score",
    "test_generation": "tests_generate",
    "simulation": "simulation_run",
    "governance_gate": "governance_evaluate",
    "governance_evaluate": "governance_evaluate",
    "pack_generation": "pack_generate",
    "policy_ingest": "policy_ingest",
}


def build_workflow_trace_summary(session_id: str, session: dict[str, Any] | None = None) -> dict[str, Any]:
    status = get_workflow_status(session_id)
    if session:
        status["contract_approved"] = bool(session.get("contract_approved"))
        status["impact_analyzed"] = bool(session.get("impact_json"))
        status["graph_persisted"] = bool(session.get("graph_json"))
        status["risks_scored"] = bool(session.get("risks_json"))
        status["tests_generated"] = bool(session.get("tests_json"))
        status["simulation_run"] = bool(session.get("simulation_json"))
        status["governance_passed"] = bool(session.get("governance_json"))
        if not status.get("policy_guidance"):
            from app.services.policy_graph import extract_workflow_guidance

            status["policy_guidance"] = extract_workflow_guidance(session.get("domain", "procurement"))

    current_step = status.get("current_step", "intake")
    langfuse = langfuse_status()

    completed_flags: dict[str, bool] = {
        "policy_graph_load": bool(status.get("policy_guidance", {}).get("configured")),
        "contract_compile": bool(session and session.get("contract_json")),
        "human_approval_gate": bool(status.get("contract_approved")),
        "impact_analysis": bool(status.get("impact_analyzed")),
        "graph_persist": bool(status.get("graph_persisted")),
        "risk_scoring": bool(status.get("risks_scored")),
        "test_generation": bool(status.get("tests_generated")),
        "simulation": bool(status.get("simulation_run")),
        "governance_gate": bool(status.get("governance_passed")),
        "pack_generation": bool(status.get("pack_generated")),
    }

    steps: list[dict[str, Any]] = []
    for step_name in STEP_ORDER:
        if step_name == "intake":
            step_status = "completed" if current_step != "intake" else "active"
        elif step_name == current_step:
            step_status = "active"
        elif completed_flags.get(step_name):
            step_status = "completed"
        elif _step_index(step_name) < _step_index(current_step):
            step_status = "completed"
        else:
            step_status = "pending"

        if status.get("gate_status") == "blocked" and step_name == current_step:
            step_status = "blocked"

        steps.append(
            {
                "id": step_name,
                "status": step_status,
                "api_action": STEP_TO_API_ACTION.get(step_name),
            }
        )

    return {
        "session_id": session_id,
        "current_step": current_step,
        "gate_status": status.get("gate_status", "open"),
        "blocked_reason": status.get("blocked_reason"),
        "steps": steps,
        "all_steps": ALL_WORKFLOW_STEPS,
        "langfuse": {
            **langfuse,
            "session_trace_url": build_session_trace_url(session_id),
        },
    }


def _step_index(step_name: str) -> int:
    try:
        return STEP_ORDER.index(step_name)
    except ValueError:
        return -1

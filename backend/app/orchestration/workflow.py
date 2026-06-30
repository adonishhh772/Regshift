"""LangGraph workflow orchestration for RegShift change sessions.

Architecture
------------
LangGraph owns the **state machine**: step order, human-interrupt gates, and
prerequisite enforcement via ``validate_action()``. FastAPI endpoints invoke
the domain services (impact analysis, risk scoring, test generation,
simulation) and persist results to the session store; LangGraph state is then
synced with ``sync_workflow_state()``.

This split is intentional for production:
- **LangGraph** — durable workflow state, gate interrupts, audit trail of steps
- **FastAPI services** — idempotent, testable business logic callable from API or batch jobs

Nodes that only advance flags (``node_impact_analysis``, ``node_risk_scoring``,
``node_simulation``) mark steps complete when the corresponding API endpoint
has already run the service and stored JSON on the session. Nodes with real work
(``node_policy_graph_load``) run lightweight orchestration inline when the graph
is invoked directly.
"""

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.orchestration.state import WorkflowState

STEP_ORDER = [
    "intake",
    "policy_graph_load",
    "contract_compile",
    "human_approval_gate",
    "index_scan",
    "impact_analysis",
    "graph_persist",
    "risk_scoring",
    "test_generation",
    "simulation",
    "governance_gate",
    "pack_generation",
]

HUMAN_GATES = {"human_approval_gate", "governance_gate"}


def _advance_step(state: WorkflowState, next_step: str) -> WorkflowState:
    return {**state, "current_step": next_step}


def node_intake(state: WorkflowState) -> WorkflowState:
    return _advance_step(state, "policy_graph_load")


def node_policy_graph_load(state: WorkflowState) -> WorkflowState:
    from app.services.policy_graph import extract_workflow_guidance
    from app.services.langfuse_tracer import WORKFLOW_STEP_POLICY_GRAPH_LOAD, trace_regshift_step

    domain = state.get("domain", "procurement")
    session_id = state.get("session_id", "unknown")

    with trace_regshift_step(WORKFLOW_STEP_POLICY_GRAPH_LOAD, session_id, domain=domain):
        guidance = extract_workflow_guidance(domain)

    if not guidance.get("configured"):
        return {
            **state,
            "current_step": "policy_graph_load",
            "gate_status": "blocked",
            "blocked_reason": guidance.get("message"),
            "policy_guidance": guidance,
        }

    return {
        **state,
        "policy_guidance": guidance,
        "gate_status": "open",
        "blocked_reason": None,
        "current_step": "contract_compile",
    }


def node_contract_compile(state: WorkflowState) -> WorkflowState:
    return _advance_step(state, "human_approval_gate")


def node_human_approval_gate(state: WorkflowState) -> WorkflowState:
    if not state.get("contract_approved"):
        return {
            **state,
            "current_step": "human_approval_gate",
            "gate_status": "blocked",
            "blocked_reason": "Change Contract requires human approval before impact analysis",
        }
    return {**state, "gate_status": "open", "blocked_reason": None, "current_step": "index_scan"}


def node_index_scan(state: WorkflowState) -> WorkflowState:
    """Marks index scan complete; actual scan runs via POST /api/index/scan."""
    return {**state, "index_scanned": True, "current_step": "impact_analysis"}


def node_impact_analysis(state: WorkflowState) -> WorkflowState:
    """Gate flag only — impact work runs in POST /api/impact/analyze (analyze_impact service)."""
    return {**state, "impact_analyzed": True, "current_step": "graph_persist"}


def node_graph_persist(state: WorkflowState) -> WorkflowState:
    return {**state, "graph_persisted": True, "current_step": "risk_scoring"}


def node_risk_scoring(state: WorkflowState) -> WorkflowState:
    """Gate flag only — risk scoring runs in POST /api/risk/score (score_risks service)."""
    return {**state, "risks_scored": True, "current_step": "test_generation"}


def node_test_generation(state: WorkflowState) -> WorkflowState:
    """Gate flag only — tests run in POST /api/tests/generate (generate_tests service)."""
    return {**state, "tests_generated": True, "current_step": "simulation"}


def node_simulation(state: WorkflowState) -> WorkflowState:
    """Gate flag only — simulation runs in POST /api/simulation/run (run_simulation service)."""
    return {**state, "simulation_run": True, "current_step": "governance_gate"}


def node_governance_gate(state: WorkflowState) -> WorkflowState:
    if not state.get("governance_passed"):
        return {
            **state,
            "current_step": "governance_gate",
            "gate_status": "blocked",
            "blocked_reason": "Production governance evaluation has not passed",
        }
    return {**state, "gate_status": "open", "current_step": "pack_generation"}


def node_pack_generation(state: WorkflowState) -> WorkflowState:
    return {**state, "pack_generated": True, "current_step": "completed"}


def route_after_human_gate(state: WorkflowState) -> str:
    if state.get("contract_approved"):
        return "index_scan"
    return END


def route_after_governance(state: WorkflowState) -> str:
    if state.get("governance_passed"):
        return "pack_generation"
    return END


def build_workflow():
    graph = StateGraph(WorkflowState)
    graph.add_node("intake", node_intake)
    graph.add_node("policy_graph_load", node_policy_graph_load)
    graph.add_node("contract_compile", node_contract_compile)
    graph.add_node("human_approval_gate", node_human_approval_gate)
    graph.add_node("index_scan", node_index_scan)
    graph.add_node("impact_analysis", node_impact_analysis)
    graph.add_node("graph_persist", node_graph_persist)
    graph.add_node("risk_scoring", node_risk_scoring)
    graph.add_node("test_generation", node_test_generation)
    graph.add_node("simulation", node_simulation)
    graph.add_node("governance_gate", node_governance_gate)
    graph.add_node("pack_generation", node_pack_generation)

    graph.set_entry_point("intake")
    graph.add_edge("intake", "policy_graph_load")
    graph.add_edge("policy_graph_load", "contract_compile")
    graph.add_edge("contract_compile", "human_approval_gate")
    graph.add_conditional_edges("human_approval_gate", route_after_human_gate, {"index_scan": "index_scan", END: END})
    graph.add_edge("index_scan", "impact_analysis")
    graph.add_edge("impact_analysis", "graph_persist")
    graph.add_edge("graph_persist", "risk_scoring")
    graph.add_edge("risk_scoring", "test_generation")
    graph.add_edge("test_generation", "simulation")
    graph.add_edge("simulation", "governance_gate")
    graph.add_conditional_edges("governance_gate", route_after_governance, {"pack_generation": "pack_generation", END: END})
    graph.add_edge("pack_generation", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer, interrupt_before=["human_approval_gate", "governance_gate"])


_workflow_app = build_workflow()


def get_workflow():
    return _workflow_app


def init_workflow_state(session_id: str, business_text: str, domain: str) -> WorkflowState:
    return WorkflowState(
        session_id=session_id,
        business_text=business_text,
        domain=domain,
        contract_approved=False,
        current_step="intake",
        gate_status="open",
        blocked_reason=None,
    )


def sync_workflow_state(session_id: str, updates: dict[str, Any]) -> WorkflowState:
    config = {"configurable": {"thread_id": session_id}}
    current = _workflow_app.get_state(config)
    base: WorkflowState = dict(current.values) if current.values else init_workflow_state(session_id, "", "procurement")
    merged: WorkflowState = {**base, **updates, "session_id": session_id}
    _workflow_app.update_state(config, merged)
    return merged


def get_workflow_status(session_id: str) -> WorkflowState:
    config = {"configurable": {"thread_id": session_id}}
    snapshot = _workflow_app.get_state(config)
    if snapshot.values:
        return dict(snapshot.values)
    return WorkflowState(session_id=session_id, current_step="intake", gate_status="open")


def validate_action(session_id: str, action: str) -> tuple[bool, str | None]:
    from app.database import session_store

    status = get_workflow_status(session_id)
    session = session_store.get_session(session_id)
    if session:
        status["contract_approved"] = bool(session.get("contract_approved"))
        status["impact_analyzed"] = bool(session.get("impact_json"))
        status["risks_scored"] = bool(session.get("risks_json"))
        status["tests_generated"] = bool(session.get("tests_json"))
        status["simulation_run"] = bool(session.get("simulation_json"))
        status["governance_passed"] = bool(session.get("governance_json"))
        status["pack_generated"] = bool(session.get("pack_id"))
        if not status.get("policy_guidance"):
            from app.services.policy_graph import extract_workflow_guidance

            domain = session.get("domain", "procurement")
            status["policy_guidance"] = extract_workflow_guidance(domain)

    requirements: dict[str, list[str]] = {
        "contract_generate": ["policy_graph_loaded"],
        "impact_analyze": ["contract_approved"],
        "graph_persist": ["contract_approved"],
        "risk_score": ["impact_analyzed"],
        "tests_generate": ["risks_scored"],
        "simulation_run": ["tests_generated"],
        "governance_evaluate": ["simulation_run"],
        "pack_generate": ["governance_passed"],
        "implement_apply": ["pack_generated"],
    }
    flags = {
        "policy_graph_loaded": bool(status.get("policy_guidance", {}).get("configured")),
        "contract_approved": status.get("contract_approved", False),
        "impact_analyzed": status.get("impact_analyzed", False),
        "risks_scored": status.get("risks_scored", False),
        "tests_generated": status.get("tests_generated", False),
        "simulation_run": status.get("simulation_run", False),
        "governance_passed": _governance_passed(session),
        "pack_generated": bool(session and session.get("pack_id")),
    }
    required = requirements.get(action, [])
    for requirement in required:
        if not flags.get(requirement, False):
            return False, f"Action '{action}' blocked: missing requirement '{requirement}'"
    return True, None


def _governance_passed(session: dict | None) -> bool:
    if not session or not session.get("governance_json"):
        return False
    import json

    data = json.loads(session["governance_json"])
    return bool(data.get("passed"))

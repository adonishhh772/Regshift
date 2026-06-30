"""Autonomous workflow agent — chains all assurance steps with human gates."""

from typing import Any, Literal

from fastapi import HTTPException

from app.database import session_store
from app.models.schemas import (
    AgentTraceEvent,
    AgentWorkflowResult,
    ClassifyRequest,
    ContractApproveRequest,
    ContractGenerateRequest,
    ImpactAnalyzeRequest,
    PackGenerateRequest,
    TraceStatus,
)
from app.services.langfuse_tracer import flush_traces
from app.services.policy_graph import extract_workflow_guidance


AgentStatus = Literal["completed", "paused", "blocked"]


def _load_session_snapshot(session_id: str) -> dict[str, Any]:
    import json

    session = session_store.get_session(session_id)
    if session is None:
        return {}

    impact = json.loads(session.get("impact_json") or "{}")
    graph = json.loads(session.get("graph_json") or "{}")
    risks = json.loads(session.get("risks_json") or "{}")
    tests = json.loads(session.get("tests_json") or "[]")
    simulation = json.loads(session.get("simulation_json") or "{}")

    return {
        "processes": impact.get("processes", []),
        "modules": impact.get("modules", []),
        "impacted_file_count": len(impact.get("files", [])),
        "graph_node_count": len(graph.get("nodes", [])),
        "graph_edge_count": len(graph.get("edges", [])),
        "tests_count": len(tests),
        "simulation_summary": simulation.get("summary"),
        "autonomous_change_allowed": risks.get("autonomous_change_allowed"),
    }


def _build_result(
    session_id: str,
    status: AgentStatus,
    summary: str,
    *,
    pause_gate: str | None = None,
    domain: str | None = None,
    confidence: float | None = None,
    contract_yaml: str | None = None,
    contract_approved: bool = False,
    pack_filename: str | None = None,
    pack_markdown: str | None = None,
    governance_passed: bool | None = None,
) -> AgentWorkflowResult:
    trace = session_store.get_trace(session_id).get_events()
    snapshot = _load_session_snapshot(session_id)
    return AgentWorkflowResult(
        session_id=session_id,
        status=status,
        pause_gate=pause_gate,
        summary=summary,
        domain=domain,
        confidence=confidence,
        contract_yaml=contract_yaml,
        contract_approved=contract_approved,
        pack_filename=pack_filename,
        pack_markdown=pack_markdown,
        governance_passed=governance_passed,
        processes=snapshot.get("processes", []),
        modules=snapshot.get("modules", []),
        impacted_file_count=snapshot.get("impacted_file_count", 0),
        graph_node_count=snapshot.get("graph_node_count", 0),
        graph_edge_count=snapshot.get("graph_edge_count", 0),
        tests_count=snapshot.get("tests_count", 0),
        simulation_summary=snapshot.get("simulation_summary"),
        autonomous_change_allowed=snapshot.get("autonomous_change_allowed"),
        trace=trace,
    )


def run_agent_start(text: str, session_id: str | None = None) -> AgentWorkflowResult:
    from app.main import change_classify, contract_generate

    classify = change_classify(ClassifyRequest(text=text, session_id=session_id))
    session_id = classify.session_id
    trace = session_store.get_trace(session_id)
    trace.emit(
        "Agent orchestrator started",
        explanation="Running classify → contract compile until human approval gate",
    )
    trace.emit(
        "Agent classified change request",
        explanation=f"Domain: {classify.domain} · confidence {classify.confidence:.0%}",
    )

    guidance = extract_workflow_guidance(classify.domain)
    if not guidance.get("configured"):
        flush_traces()
        return _build_result(
            session_id,
            "blocked",
            guidance.get("message", "Ingest a tenant policy before running the agent."),
            pause_gate="policy",
            domain=classify.domain,
            confidence=classify.confidence,
        )

    trace.emit(
        "Compiling change contract",
        explanation="Extracting machine-checkable obligations from policy graph",
    )

    contract = contract_generate(
        ContractGenerateRequest(text=text, session_id=session_id, domain=classify.domain)
    )
    trace.emit(
        "Agent paused for human approval",
        status=TraceStatus.BLOCKED,
        explanation="Review the change contract, then approve to let the agent continue",
    )
    flush_traces()

    return _build_result(
        session_id,
        "paused",
        (
            f"Classified as {classify.domain} ({round(classify.confidence * 100)}% confidence). "
            "Change contract compiled. Say \"approve contract\" and the agent will run impact analysis, "
            "simulation, governance, and pack generation automatically."
        ),
        pause_gate="human_approval",
        domain=classify.domain,
        confidence=classify.confidence,
        contract_yaml=contract.contract_yaml,
        contract_approved=False,
    )


def run_agent_resume(session_id: str) -> AgentWorkflowResult:
    from app.main import (
        contract_approve,
        governance_evaluate,
        impact_analyze,
        pack_generate,
        simulation_run,
    )

    session = session_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    trace = session_store.get_trace(session_id)
    trace.emit(
        "Agent resuming assurance workflow",
        explanation="Running impact → simulation → governance → change pack",
    )

    if not session.get("contract_yaml"):
        flush_traces()
        return _build_result(
            session_id,
            "blocked",
            "No change contract found. Describe your change first so the agent can compile a contract.",
            pause_gate="human_approval",
            domain=session.get("domain"),
        )

    if not session.get("contract_approved"):
        contract_approve(
            ContractApproveRequest(session_id=session_id, contract_yaml=session["contract_yaml"])
        )
        trace.emit("Agent recorded contract approval", explanation="Human gate passed")

    impact_analyze(ImpactAnalyzeRequest(session_id=session_id))
    trace.emit(
        "Agent completed impact analysis",
        explanation="Knowledge graph, tests, and risk scoring finished",
    )

    simulation_run(session_id=session_id)
    evaluation = governance_evaluate(session_id=session_id)

    if not evaluation.passed:
        flush_traces()
        return _build_result(
            session_id,
            "blocked",
            f"Production gate blocked: {evaluation.summary}",
            pause_gate="governance",
            domain=session.get("domain"),
            contract_yaml=session.get("contract_yaml"),
            contract_approved=True,
            governance_passed=False,
        )

    pack = pack_generate(PackGenerateRequest(session_id=session_id))
    trace.emit(
        "Agent completed full assurance workflow",
        explanation=f"Change pack ready: {pack.filename}",
    )
    flush_traces()

    snapshot = _load_session_snapshot(session_id)
    summary = (
        f"Assurance workflow complete.\n\n"
        f"• {snapshot.get('graph_node_count', 0)} graph nodes · "
        f"{snapshot.get('impacted_file_count', 0)} impacted files\n"
        f"• {snapshot.get('tests_count', 0)} contract tests\n"
        f"• Simulation: {snapshot.get('simulation_summary', 'done')}\n"
        f"• Production gate: PASSED\n"
        f"• Change pack: {pack.filename}"
    )

    return _build_result(
        session_id,
        "completed",
        summary,
        domain=session.get("domain"),
        contract_yaml=session.get("contract_yaml"),
        contract_approved=True,
        pack_filename=pack.filename,
        pack_markdown=pack.markdown,
        governance_passed=True,
    )

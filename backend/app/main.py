import json
import logging
import threading
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.logging_config import configure_logging
from app.middleware.http_logging import HttpLoggingMiddleware

from app.database import init_db, session_store
from app.models.schemas import (
    AgentTraceEvent,
    AgentWorkflowResumeRequest,
    AgentWorkflowResult,
    AgentWorkflowStartRequest,
    ClassifyRequest,
    ClassifyResponse,
    ContractApproveRequest,
    ContractGenerateRequest,
    ContractResponse,
    DomainAlternative,
    GovernanceConfigResponse,
    GovernanceEvaluation,
    GraphResponse,
    GraphNode,
    GraphEdge,
    GovernanceEvaluateResponse,
    HealthResponse,
    ImpactAnalyzeRequest,
    ImpactResponse,
    IndexStatusResponse,
    DashboardStatsResponse,
    DashboardDomainCount,
    DomainPackListResponse,
    DomainPackSummary,
    OrchestrationStatusResponse,
    PackGenerateRequest,
    PackResponse,
    ImplementApplyRequest,
    ImplementApplyResponse,
    CodePatchRecord,
    PackLoadRequest,
    PackLoadResponse,
    PolicyIngestRequest,
    PolicyIngestResponse,
    PolicyListResponse,
    PolicyActivateResponse,
    PolicyDocument,
    PolicyRule,
    RiskAssessment,
    RiskScoreRequest,
    RiskScoreResponse,
    SessionDetailResponse,
    SessionListResponse,
    SessionSummary,
    SimulationResponse,
    SystemConfirmRequest,
    SystemGraphResponse,
    SystemIdentification,
    SystemIngestAllResponse,
    SystemIngestResponse,
    SystemListResponse,
    SystemSummary,
    IdentifiedSystem,
    TestGenerateResponse,
    TraceStatus,
)
from app.orchestration.workflow import get_workflow_status, init_workflow_state, sync_workflow_state, validate_action
from app.services.classifier import classify_change
from app.services.domain_loader import load_all_domain_packs
from app.services.contract_compiler import compile_contract, parse_contract_yaml
from app.services.change_overlay_graph import apply_change_overlay
from app.services.graph_builder import build_graph
from app.services.erpnext_implementor import apply_change_contract_to_erpnext
from app.services.system_catalog import ensure_workspace_repo_links, list_catalog_summaries
from app.services.system_identifier import identify_systems
from app.services.system_ingestor import ingest_all_systems, ingest_system
from app.services.system_graph_store import load_system_graph
from app.services.implementation_graph import extend_graph_with_implementation
from app.services.impact_analyzer import analyze_impact
from app.services.neo4j_store import load_session_graph, neo4j_status, persist_session_graph, trace_obligation_path
from app.services.pack_generator import generate_change_pack, read_change_pack
from app.services.policy_governance import evaluate_production_gate
from app.services.policy_compiler import build_governance_config
from app.services.policy_ingestor import ingest_policy_document
from app.services.policy_seed import seed_demo_policies
from app.services.policy_store import (
    activate_policy,
    count_active_policies,
    get_active_policy,
    get_policy,
    ingest_policy,
    list_policies,
)
from app.services.langfuse_tracer import (
    WORKFLOW_STEP_CLASSIFY,
    WORKFLOW_STEP_CONTRACT_COMPILE,
    WORKFLOW_STEP_GOVERNANCE_EVALUATE,
    WORKFLOW_STEP_GRAPH_PERSIST,
    WORKFLOW_STEP_HUMAN_APPROVAL,
    WORKFLOW_STEP_IMPACT_ANALYSIS,
    WORKFLOW_STEP_INDEX_SCAN,
    WORKFLOW_STEP_PACK_GENERATION,
    WORKFLOW_STEP_POLICY_INGEST,
    WORKFLOW_STEP_RISK_SCORING,
    WORKFLOW_STEP_SIMULATION,
    WORKFLOW_STEP_TEST_GENERATION,
    flush_traces,
    langfuse_status,
    probe_langfuse_connectivity,
    reset_langfuse_client,
    trace_nested_step,
    trace_policy_extraction,
    trace_regshift_step,
    verify_langfuse_connection,
)
from app.services.workflow_trace import build_workflow_trace_summary
from app.services.policy_graph import (
    extract_workflow_guidance,
    get_policy_graph_visualization,
    persist_policy_knowledge_graph,
)
from app.services.llm.gateway import gateway_status
from app.services.risk_engine import score_risks
from app.services.scanner import get_index_status, scan_index
from app.services.simulator import run_simulation
from app.services.test_generator import generate_tests
from app.streaming import create_sse_response

configure_logging()

logger = logging.getLogger(__name__)

app = FastAPI(title="RegShift API", version="1.0.0")

_LANGFUSE_REFRESH_COOLDOWN_SECONDS = 60.0
_last_langfuse_refresh_monotonic = 0.0

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(HttpLoggingMiddleware)


@app.on_event("startup")
def on_startup() -> None:
    logger.info("RegShift API starting")
    init_db()
    settings_paths()
    reset_langfuse_client()
    threading.Thread(
        target=_probe_neo4j_background,
        name="neo4j-probe",
        daemon=True,
    ).start()
    threading.Thread(
        target=_probe_langfuse_background,
        name="langfuse-probe",
        daemon=True,
    ).start()
    threading.Thread(
        target=_startup_background,
        name="startup-background",
        daemon=True,
    ).start()
    logger.info("RegShift API startup complete")


def _startup_background() -> None:
    try:
        ensure_workspace_repo_links()
        ingest_result = ingest_all_systems()
        logger.info(
            "System KG ingest complete total=%s succeeded=%s",
            ingest_result.get("total"),
            ingest_result.get("succeeded"),
        )
    except Exception as error:
        logger.warning("System KG ingest failed error=%s", error)
    try:
        status = get_index_status()
        if status["file_count"] == 0:
            logger.info("Code index empty — seeding procurement scan")
            scan_index("procurement")
        else:
            logger.info("Code index ready file_count=%s", status["file_count"])
    except Exception as error:
        logger.warning("Startup index scan failed error=%s", error)
    try:
        from app.config import settings

        if settings.seed_demo_policies:
            seed_demo_policies()
            logger.info("Demo policies seeded")
    except Exception as error:
        logger.warning("Demo policy seed failed error=%s", error)


def _probe_neo4j_background() -> None:
    try:
        from app.services.neo4j_store import neo4j_status, probe_neo4j_connectivity

        probe_neo4j_connectivity()
        status = neo4j_status()
        logger.info(
            "Neo4j probe complete available=%s backend=%s",
            status.get("available"),
            status.get("backend"),
        )
    except Exception as error:
        logger.warning("Neo4j probe failed error=%s", error)


def _probe_langfuse_background() -> None:
    try:
        result = probe_langfuse_connectivity()
        logger.info(
            "Langfuse probe complete authenticated=%s reason=%s",
            result.get("authenticated"),
            result.get("reason"),
        )
    except Exception as error:
        logger.warning("Langfuse probe failed error=%s", error)


def settings_paths() -> None:
    from app.config import settings

    settings.generated_packs_dir.mkdir(parents=True, exist_ok=True)


def _resolve_session(session_id: str | None) -> dict[str, Any]:
    if session_id:
        session = session_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    session = session_store.get_latest_session()
    if not session:
        raise HTTPException(status_code=404, detail="No active session")
    return session


def _sync_policy_guidance(session_id: str, domain: str) -> dict[str, Any]:
    guidance = extract_workflow_guidance(domain)
    sync_workflow_state(
        session_id,
        {
            "policy_guidance": guidance,
            "current_step": "contract_compile" if guidance.get("configured") else "policy_graph_load",
            "gate_status": "open" if guidance.get("configured") else "blocked",
            "blocked_reason": None if guidance.get("configured") else guidance.get("message"),
        },
    )
    return guidance


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="regshift-backend",
        neo4j=neo4j_status(),
        langfuse=langfuse_status(),
        llm=gateway_status(),
        orchestration="langgraph",
    )


@app.post("/api/langfuse/refresh")
def langfuse_refresh() -> dict[str, Any]:
    global _last_langfuse_refresh_monotonic
    now = time.monotonic()
    if now - _last_langfuse_refresh_monotonic < _LANGFUSE_REFRESH_COOLDOWN_SECONDS:
        status = langfuse_status()
        return {
            "langfuse": status,
            "authenticated": bool(status.get("authenticated")),
            "reason": "Refresh cooldown active",
            "skipped": True,
        }
    _last_langfuse_refresh_monotonic = now
    reset_langfuse_client()
    verification = verify_langfuse_connection()
    status = langfuse_status()
    return {"langfuse": status, **verification}


@app.get("/api/index/status", response_model=IndexStatusResponse)
def index_status() -> IndexStatusResponse:
    status = get_index_status()
    return IndexStatusResponse(**status)


def _session_summary_from_row(row: dict[str, Any]) -> SessionSummary:
    return SessionSummary(
        id=row["id"],
        business_text=row["business_text"],
        domain=row.get("domain"),
        contract_approved=bool(row.get("contract_approved")),
        has_contract=bool(row.get("contract_yaml")),
        pack_id=row.get("pack_id"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@app.get("/api/sessions", response_model=SessionListResponse)
def list_sessions(limit: int = 50) -> SessionListResponse:
    rows = session_store.list_sessions(limit=min(limit, 100))
    sessions = [_session_summary_from_row(row) for row in rows]
    return SessionListResponse(sessions=sessions, total=len(sessions))


@app.get("/api/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session_detail(session_id: str) -> SessionDetailResponse:
    session = session_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    contract: dict[str, Any] | None = None
    raw_contract = session.get("contract_json")
    if raw_contract:
        try:
            parsed = json.loads(raw_contract)
            contract = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            contract = None

    return SessionDetailResponse(
        id=session["id"],
        business_text=session.get("business_text", ""),
        domain=session.get("domain"),
        contract_yaml=session.get("contract_yaml"),
        contract=contract,
        contract_approved=bool(session.get("contract_approved")),
        pack_id=session.get("pack_id"),
        created_at=session["created_at"],
        updated_at=session["updated_at"],
    )


@app.get("/api/domain-packs", response_model=DomainPackListResponse)
def list_domain_packs() -> DomainPackListResponse:
    packs: list[DomainPackSummary] = []
    for domain, data in load_all_domain_packs().items():
        packs.append(
            DomainPackSummary(
                domain=domain,
                display_name=str(data.get("display_name") or data.get("domain_name") or domain).replace("_", " ").title(),
                description=str(data.get("description", "")),
                process_count=len(data.get("processes", []) or []),
                module_count=len(data.get("modules", []) or []),
            )
        )
    packs.sort(key=lambda pack: pack.domain)
    return DomainPackListResponse(packs=packs)


@app.get("/api/dashboard/stats", response_model=DashboardStatsResponse)
def dashboard_stats() -> DashboardStatsResponse:
    rows = session_store.list_sessions(limit=100)
    domain_counts: dict[str, int] = {}
    sessions_with_contracts = 0
    approved_contracts = 0
    change_packs = 0
    for row in rows:
        domain = row.get("domain") or "unknown"
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
        if row.get("contract_yaml"):
            sessions_with_contracts += 1
        if row.get("contract_approved"):
            approved_contracts += 1
        if row.get("pack_id"):
            change_packs += 1
    index_status = get_index_status()
    policies = list_policies()
    neo4j = neo4j_status()
    return DashboardStatsResponse(
        total_sessions=len(rows),
        sessions_with_contracts=sessions_with_contracts,
        approved_contracts=approved_contracts,
        change_packs=change_packs,
        indexed_files=index_status["file_count"],
        index_source=index_status["source"],
        active_policies=count_active_policies(),
        domain_packs=len(load_all_domain_packs()),
        sessions_by_domain=[
            DashboardDomainCount(domain=domain, count=count)
            for domain, count in sorted(domain_counts.items(), key=lambda item: item[1], reverse=True)
        ],
        graph_backend="neo4j" if neo4j.get("available") else str(neo4j.get("backend", "networkx_fallback")),
        backend_status="ok",
    )


def _policy_document_from_row(policy: dict) -> PolicyDocument:
    return PolicyDocument(
        id=policy["id"],
        tenant_id=policy["tenant_id"],
        title=policy["title"],
        domain=policy["domain"],
        source_text=policy["source_text"],
        version=policy["version"],
        status=policy["status"],
        rules=policy["rules"],
        created_at=policy["created_at"],
        updated_at=policy["updated_at"],
    )


@app.post("/api/policy/ingest", response_model=PolicyIngestResponse)
def policy_ingest(request: PolicyIngestRequest) -> PolicyIngestResponse:
    policy_session_id = f"policy-{request.domain or 'global'}"
    with trace_regshift_step(
        WORKFLOW_STEP_POLICY_INGEST,
        policy_session_id,
        domain=request.domain,
        input_data={"title": request.title},
    ) as step_output:
        parsed = ingest_policy_document(
            title=request.title,
            source_text=request.source_text,
            domain=request.domain,
            session_id=policy_session_id,
        )
        stored = ingest_policy(
            title=parsed["title"],
            source_text=request.source_text,
            rules=parsed,
            domain=parsed["domain"],
        )
        graph_result = persist_policy_knowledge_graph(stored["tenant_id"], stored)
        trace_policy_extraction(
            session_id=policy_session_id,
            policy_id=stored["id"],
            domain=parsed["domain"],
            extracted_rules=parsed["rules"],
        )
        step_output["data"] = {
            "policy_id": stored["id"],
            "rule_count": parsed["rule_count"],
            "graph_backend": graph_result.get("backend"),
        }

    extracted_rules = [
        PolicyRule(
            id=rule["id"],
            type=rule["type"],
            value=rule.get("value"),
            key=rule.get("key"),
            citation=rule["citation"],
            description=rule["description"],
        )
        for rule in parsed["rules"]
    ]
    flush_traces()
    return PolicyIngestResponse(
        policy=_policy_document_from_row(stored),
        extracted_rules=extracted_rules,
        rule_count=parsed["rule_count"],
        trace=[
            AgentTraceEvent(
                timestamp=stored["created_at"],
                message=f"Ingested tenant policy: {stored['title']}",
                status=TraceStatus.COMPLETED,
                explanation=(
                    f"Extracted {parsed['rule_count']} rules · "
                    f"Knowledge graph: {graph_result.get('backend', 'unknown')}"
                ),
                evidence_count=parsed["rule_count"],
            )
        ],
    )


@app.get("/api/policy/list", response_model=PolicyListResponse)
def policy_list() -> PolicyListResponse:
    policies = list_policies()
    active_domains = sorted(
        {
            policy["domain"]
            for policy in policies
            if policy["status"] == "active" and policy["domain"]
        }
    )
    return PolicyListResponse(
        policies=[_policy_document_from_row(policy) for policy in policies],
        active_domains=active_domains,
    )


@app.get("/api/policy/{policy_id}", response_model=PolicyDocument)
def policy_get(policy_id: str) -> PolicyDocument:
    policy = get_policy(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")
    return _policy_document_from_row(policy)


@app.post("/api/policy/{policy_id}/activate", response_model=PolicyActivateResponse)
def policy_activate(policy_id: str) -> PolicyActivateResponse:
    policy = activate_policy(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found or cannot be activated")
    graph_result = persist_policy_knowledge_graph(policy["tenant_id"], policy)
    flush_traces()
    return PolicyActivateResponse(
        policy=_policy_document_from_row(policy),
        graph_backend=graph_result.get("backend"),
        node_count=int(graph_result.get("node_count", 0)),
    )


@app.get("/api/policy/active/{domain}", response_model=PolicyDocument)
def policy_active(domain: str) -> PolicyDocument:
    policy = get_active_policy(domain)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"No active policy for domain '{domain}'")
    return _policy_document_from_row(policy)


@app.get("/api/policy/governance/{domain}", response_model=GovernanceConfigResponse)
def policy_governance_config(domain: str) -> GovernanceConfigResponse:
    config = build_governance_config(domain)
    if config is None:
        return GovernanceConfigResponse(domain=domain, configured=False)
    return GovernanceConfigResponse(
        domain=domain,
        configured=True,
        policy_id=config["policy_id"],
        policy_title=config["policy_title"],
        policy_version=config["policy_version"],
        obligations=config["obligations"],
        threshold=config["threshold"],
        approval_roles=config["approval_roles"],
        agent_limits=config["agent_limits"],
        citations=config["citations"],
    )


@app.get("/api/policy/graph/{domain}")
def policy_graph(domain: str, policy_id: str | None = None) -> dict[str, Any]:
    return get_policy_graph_visualization(domain, policy_id=policy_id)


@app.post("/api/policy/rebuild-graph/{domain}")
def rebuild_policy_graph(domain: str) -> dict[str, Any]:
    policy = get_active_policy(domain)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"No active policy for domain: {domain}")
    return persist_policy_knowledge_graph(policy["tenant_id"], policy)


@app.get("/api/policy/workflow-guidance/{domain}")
def policy_workflow_guidance(domain: str) -> dict[str, Any]:
    return extract_workflow_guidance(domain)


@app.get("/api/traces/workflow/{session_id}")
def workflow_trace_summary(session_id: str) -> dict[str, Any]:
    session = _resolve_session(session_id)
    return build_workflow_trace_summary(session_id, session)


@app.post("/api/index/scan", response_model=IndexStatusResponse)
def index_scan() -> IndexStatusResponse:
    with trace_regshift_step(
        WORKFLOW_STEP_INDEX_SCAN,
        session_id="system-index",
        domain="procurement",
    ) as step_output:
        try:
            result = scan_index("procurement")
            step_output["data"] = {"file_count": result["file_count"], "source": result["source"]}
            flush_traces()
            return IndexStatusResponse(**result)
        except FileNotFoundError as error:
            step_output["status"] = "error"
            flush_traces()
            raise HTTPException(status_code=404, detail=str(error)) from error


def _system_identification_to_model(payload: dict[str, Any]) -> SystemIdentification:
    return SystemIdentification(
        primary_system_id=payload.get("primary_system_id"),
        systems=[
            IdentifiedSystem(
                system_id=item["system_id"],
                name=item["name"],
                vendor=item["vendor"],
                confidence=item["confidence"],
                role=item["role"],
                ingested=item.get("ingested", False),
                matched_signals=item.get("matched_signals", []),
            )
            for item in payload.get("systems", [])
        ],
        needs_confirmation=payload.get("needs_confirmation", False),
        confirmed=payload.get("confirmed", False),
    )


@app.get("/api/systems", response_model=SystemListResponse)
def systems_list() -> SystemListResponse:
    summaries = list_catalog_summaries()
    return SystemListResponse(
        systems=[SystemSummary(**summary) for summary in summaries],
        total=len(summaries),
    )


@app.post("/api/systems/ingest", response_model=SystemIngestAllResponse)
def systems_ingest_all() -> SystemIngestAllResponse:
    ensure_workspace_repo_links()
    result = ingest_all_systems()
    return SystemIngestAllResponse(
        total=result["total"],
        succeeded=result["succeeded"],
        results=[SystemIngestResponse(**item) for item in result["results"]],
    )


@app.post("/api/systems/{system_id}/ingest", response_model=SystemIngestResponse)
def systems_ingest_one(system_id: str) -> SystemIngestResponse:
    result = ingest_system(system_id)
    return SystemIngestResponse(**result)


@app.get("/api/systems/graph", response_model=SystemGraphResponse)
def systems_graph(system_id: str | None = None, limit: int = 500) -> SystemGraphResponse:
    graph = load_system_graph(system_id=system_id, limit=limit)
    return SystemGraphResponse(
        system_id=system_id,
        nodes=graph["nodes"],
        edges=graph["edges"],
    )


@app.post("/api/systems/confirm", response_model=SystemIdentification)
def systems_confirm(request: SystemConfirmRequest) -> SystemIdentification:
    session = _resolve_session(request.session_id)
    raw = session.get("target_systems_json")
    if not raw:
        raise HTTPException(status_code=400, detail="Identify systems before confirming")
    payload = json.loads(raw)
    catalog_ids = {item["system_id"] for item in payload.get("systems", [])}
    selected = [system_id for system_id in request.system_ids if system_id in catalog_ids]
    if not selected:
        raise HTTPException(status_code=400, detail="No valid systems selected")

    systems = [item for item in payload.get("systems", []) if item.get("system_id") in selected]
    for index, item in enumerate(systems):
        item["role"] = "primary" if index == 0 else "related"
    updated = {
        "primary_system_id": systems[0]["system_id"],
        "systems": systems,
        "needs_confirmation": False,
        "confirmed": True,
    }
    session_store.update_session(
        request.session_id,
        target_systems_json=json.dumps(updated),
        systems_confirmed=1,
    )
    return _system_identification_to_model(updated)


@app.post("/api/change/classify", response_model=ClassifyResponse)
def change_classify(request: ClassifyRequest) -> ClassifyResponse:
    session_id = request.session_id or session_store.create_session(request.text)
    trace = session_store.get_trace(session_id)
    trace.clear()

    with trace_regshift_step(
        WORKFLOW_STEP_CLASSIFY,
        session_id,
        input_data={"text_length": len(request.text)},
    ) as step_output:
        trace.emit("Parsed business change", explanation="Extracting intent from business request")

        result = classify_change(request.text, session_id=session_id)
        trace.emit(
            f"Classified domain as {result['domain']}",
            explanation=f"Confidence {result['confidence']}",
            evidence_count=len(result.get("alternatives", [])) + 1,
        )

        session_store.update_session(session_id, domain=result["domain"], business_text=request.text)
        systems_payload = identify_systems(request.text, result["domain"])
        session_store.update_session(session_id, target_systems_json=json.dumps(systems_payload))
        if systems_payload.get("primary_system_id"):
            primary = next(
                (item for item in systems_payload.get("systems", []) if item.get("role") == "primary"),
                None,
            )
            if primary:
                trace.emit(
                    f"Identified target system: {primary.get('name')}",
                    explanation=f"Vendor {primary.get('vendor')} · confidence {primary.get('confidence')}",
                    evidence_count=len(systems_payload.get("systems", [])),
                )
        session_store.save_trace(session_id)
        init_workflow_state(session_id, request.text, result["domain"])
        guidance = _sync_policy_guidance(session_id, result["domain"])
        if guidance.get("configured"):
            trace.emit(
                "Loaded policy knowledge graph guidance",
                explanation=f"Workflow guided by {guidance.get('policy_title', 'tenant policy')}",
                evidence_count=len(guidance.get("required_obligations", [])),
            )
        else:
            trace.emit(
                "Policy knowledge graph not configured",
                status=TraceStatus.BLOCKED,
                explanation=guidance.get("message", "Ingest tenant policy first"),
            )
        step_output["data"] = {
            "domain": result["domain"],
            "confidence": result["confidence"],
            "policy_configured": guidance.get("configured"),
        }

    flush_traces()

    return ClassifyResponse(
        session_id=session_id,
        domain=result["domain"],
        confidence=result["confidence"],
        alternatives=[
            DomainAlternative(domain=alt["domain"], score=alt["score"])
            for alt in result.get("alternatives", [])
        ],
        systems=_system_identification_to_model(systems_payload),
        trace=trace.get_events(),
    )


@app.post("/api/contract/generate", response_model=ContractResponse)
def contract_generate(request: ContractGenerateRequest) -> ContractResponse:
    session_id = request.session_id
    if not session_id:
        session_id = session_store.create_session(request.text)

    session = _resolve_session(session_id)
    trace = session_store.get_trace(session_id)

    domain = request.domain or session.get("domain") or classify_change(request.text, session_id=session_id)["domain"]
    _sync_policy_guidance(session_id, domain)
    allowed, reason = validate_action(session_id, "contract_generate")
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)

    with trace_regshift_step(
        WORKFLOW_STEP_CONTRACT_COMPILE,
        session_id,
        domain=domain,
        input_data={"text_length": len(request.text)},
    ) as step_output:
        trace.emit(f"Loaded {domain} domain pack", explanation="Applying domain-specific rules from policy knowledge graph")

        guidance = extract_workflow_guidance(domain)
        if guidance.get("configured"):
            trace.emit(
                f"Policy graph guides contract: {guidance.get('policy_title')}",
                explanation=f"Source: {guidance.get('source', 'policy_graph')}",
                evidence_count=len(guidance.get("required_obligations", [])),
            )

        compiled = compile_contract(request.text, domain, session_id=session_id)
        step_output["data"] = {
            "obligations": compiled["contract"].get("required_behaviour", []),
            "confidence": compiled["confidence"],
        }

    trace.emit("Compiled Change Contract", explanation="Machine-checkable obligations extracted from policy graph")
    trace.emit("Waiting for user approval", status=TraceStatus.BLOCKED, explanation="Human gate required")

    session_store.update_session(
        session_id,
        business_text=request.text,
        domain=domain,
        contract_yaml=compiled["contract_yaml"],
        contract_json=json.dumps(compiled["contract"]),
        contract_approved=0,
    )
    session_store.save_trace(session_id)
    flush_traces()

    return ContractResponse(
        session_id=session_id,
        domain=domain,
        contract_yaml=compiled["contract_yaml"],
        contract=compiled["contract"],
        approved=False,
        confidence=compiled["confidence"],
        trace=trace.get_events(),
    )


@app.post("/api/contract/approve", response_model=ContractResponse)
def contract_approve(request: ContractApproveRequest) -> ContractResponse:
    session = _resolve_session(request.session_id)
    trace = session_store.get_trace(request.session_id)
    domain = session.get("domain", "procurement")

    with trace_regshift_step(
        WORKFLOW_STEP_HUMAN_APPROVAL,
        request.session_id,
        domain=domain,
    ) as step_output:
        try:
            contract = parse_contract_yaml(request.contract_yaml)
        except Exception as error:
            step_output["status"] = "error"
            flush_traces()
            raise HTTPException(status_code=400, detail=f"Invalid contract YAML: {error}") from error

        trace.emit("Approved Change Contract", explanation="User confirmed contract obligations")

        session_store.update_session(
            request.session_id,
            contract_yaml=request.contract_yaml,
            contract_json=json.dumps(contract),
            contract_approved=1,
        )
        sync_workflow_state(request.session_id, {"contract_approved": True, "contract_yaml": request.contract_yaml})
        session_store.save_trace(request.session_id)
        step_output["data"] = {"approved": True, "obligations": contract.get("required_behaviour", [])}

    flush_traces()

    return ContractResponse(
        session_id=request.session_id,
        domain=session.get("domain", contract.get("domain", "procurement")),
        contract_yaml=request.contract_yaml,
        contract=contract,
        approved=True,
        trace=trace.get_events(),
    )


@app.post("/api/impact/analyze", response_model=ImpactResponse)
def impact_analyze(request: ImpactAnalyzeRequest) -> ImpactResponse:
    session = _resolve_session(request.session_id)
    allowed, reason = validate_action(request.session_id, "impact_analyze")
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)

    if not session.get("contract_approved"):
        raise HTTPException(status_code=400, detail="Contract must be approved first")

    trace = session_store.get_trace(request.session_id)
    contract = json.loads(session.get("contract_json") or "{}")
    domain = session.get("domain", "procurement")

    with trace_regshift_step(
        WORKFLOW_STEP_IMPACT_ANALYSIS,
        request.session_id,
        domain=domain,
    ) as step_output:
        trace.emit("Queried stored system knowledge graph", explanation="Impact ranked from ingested system KG")

        with trace_nested_step(WORKFLOW_STEP_INDEX_SCAN) as index_output:
            trace.emit("Loaded system catalog context", explanation="Registered business systems available")
            index_output["data"] = {"indexed": True}

        with trace_nested_step("analyze_impact") as impact_output:
            impact = analyze_impact(contract, domain, session=session)
            impact_output["data"] = {
                "file_count": len(impact["files"]),
                "modules": impact["modules"],
                "impact_source": impact.get("impact_source"),
                "target_systems": impact.get("target_systems", []),
            }

        trace.emit(
            "Ranked impacted files",
            evidence_count=len(impact["files"]),
            explanation="Evidence snippets attached to top matches",
        )

        with trace_nested_step(WORKFLOW_STEP_TEST_GENERATION) as tests_output:
            tests = [test.model_dump() for test in generate_tests(contract, domain, session_id=session["id"])]
            tests_output["data"] = {"test_count": len(tests)}

        with trace_nested_step(WORKFLOW_STEP_RISK_SCORING) as risk_output:
            risks = score_risks(contract, impact, domain)
            risk_output["data"] = {"risks": risks["risks"], "autonomous_allowed": risks["autonomous_change_allowed"]}

        with trace_nested_step("build_impact_graph") as graph_output:
            graph = build_graph(
                session.get("business_text", ""),
                contract,
                {"processes": impact["processes"], "modules": impact["modules"], "files": impact["files"]},
                risks["risks"],
                tests,
            )
            graph = apply_change_overlay(
                graph,
                contract,
                {
                    "files": impact["files"],
                    "target_systems": impact.get("target_systems", []),
                    "impact_source": impact.get("impact_source"),
                },
            )
            graph_output["data"] = {"node_count": len(graph["nodes"]), "edge_count": len(graph["edges"])}

        with trace_nested_step(WORKFLOW_STEP_GRAPH_PERSIST) as persist_output:
            neo4j_result = persist_session_graph(request.session_id, graph["nodes"], graph["edges"])
            persist_output["data"] = neo4j_result

        trace.emit(
            "Persisted knowledge graph to Neo4j" if neo4j_result["persisted"] else "Graph stored in session (Neo4j fallback)",
            explanation=f"{neo4j_result.get('node_count', 0)} nodes persisted",
            evidence_count=neo4j_result.get("edge_count", 0),
        )
        trace.emit("Built knowledge graph", explanation="Business intent mapped to system impact")

        session_store.update_session(
            request.session_id,
            impact_json=json.dumps(
                {
                    "processes": impact["processes"],
                    "modules": impact["modules"],
                    "files": [file.model_dump() for file in impact["files"]],
                }
            ),
            graph_json=json.dumps(
                {
                    "nodes": [node.model_dump() for node in graph["nodes"]],
                    "edges": [edge.model_dump() for edge in graph["edges"]],
                }
            ),
            risks_json=json.dumps(risks),
            tests_json=json.dumps(tests),
        )
        sync_workflow_state(
            request.session_id,
            {"impact_analyzed": True, "graph_persisted": True, "current_step": "risk_scoring"},
        )
        session_store.save_trace(request.session_id)
        step_output["data"] = {
            "files": len(impact["files"]),
            "graph_nodes": len(graph["nodes"]),
            "tests": len(tests),
        }

    flush_traces()

    return ImpactResponse(
        session_id=request.session_id,
        processes=impact["processes"],
        modules=impact["modules"],
        files=impact["files"],
        trace=trace.get_events(),
    )


@app.get("/api/graph/current", response_model=GraphResponse)
def graph_current(session_id: str | None = None) -> GraphResponse:
    session = _resolve_session(session_id)
    sid = session["id"]

    neo4j_graph = load_session_graph(sid)
    if neo4j_graph:
        return GraphResponse(session_id=sid, nodes=neo4j_graph["nodes"], edges=neo4j_graph["edges"])

    graph_data = json.loads(session.get("graph_json") or '{"nodes": [], "edges": []}')
    from app.models.schemas import GraphEdge, GraphNode

    nodes = [GraphNode(**node) for node in graph_data.get("nodes", [])]
    edges = [GraphEdge(**edge) for edge in graph_data.get("edges", [])]
    return GraphResponse(session_id=sid, nodes=nodes, edges=edges)


@app.get("/api/graph/trace/{obligation_node_id}")
def graph_trace_path(obligation_node_id: str, session_id: str | None = None) -> dict[str, list[str]]:
    session = _resolve_session(session_id)
    path = trace_obligation_path(session["id"], obligation_node_id)
    if not path:
        from app.services.graph_builder import get_trace_path
        from app.models.schemas import GraphEdge, GraphNode

        graph_data = json.loads(session.get("graph_json") or '{"nodes": [], "edges": []}')
        nodes = [GraphNode(**node) for node in graph_data.get("nodes", [])]
        edges = [GraphEdge(**edge) for edge in graph_data.get("edges", [])]
        path = get_trace_path({"nodes": nodes, "edges": edges}, obligation_node_id)
    return {"path": path}


@app.get("/api/orchestration/status", response_model=OrchestrationStatusResponse)
def orchestration_status(session_id: str) -> OrchestrationStatusResponse:
    status = get_workflow_status(session_id)
    neo = neo4j_status()
    return OrchestrationStatusResponse(
        session_id=session_id,
        current_step=status.get("current_step", "intake"),
        gate_status=status.get("gate_status", "open"),
        blocked_reason=status.get("blocked_reason"),
        contract_approved=bool(status.get("contract_approved")),
        governance_passed=bool(status.get("governance_passed")),
        graph_backend=neo.get("backend", "networkx_fallback"),
    )


@app.get("/api/governance/evaluate", response_model=GovernanceEvaluation)
def governance_evaluate(session_id: str) -> GovernanceEvaluation:
    session = _resolve_session(session_id)
    trace = session_store.get_trace(session_id)
    domain = session.get("domain", "procurement")

    with trace_regshift_step(
        WORKFLOW_STEP_GOVERNANCE_EVALUATE,
        session_id,
        domain=domain,
    ) as step_output:
        evaluation = evaluate_production_gate(session)
        step_output["data"] = {
            "gate_status": evaluation.gate_status,
            "passed": evaluation.passed,
            "check_count": len(evaluation.checks),
        }

    trace.emit(
        f"Production gate: {evaluation.gate_status.upper()}",
        status=TraceStatus.BLOCKED if not evaluation.passed else TraceStatus.COMPLETED,
        explanation=evaluation.summary,
        evidence_count=len(evaluation.checks),
    )

    session_store.update_session(session_id, governance_json=json.dumps(evaluation.model_dump()))
    sync_workflow_state(session_id, {"governance_passed": evaluation.passed, "gate_status": evaluation.gate_status})
    session_store.save_trace(session_id)
    flush_traces()
    return evaluation


@app.post("/api/risk/score", response_model=RiskAssessment)
def risk_score(request: RiskScoreRequest) -> RiskAssessment:
    session = _resolve_session(request.session_id)
    trace = session_store.get_trace(request.session_id)
    domain = session.get("domain", "procurement")

    with trace_regshift_step(
        WORKFLOW_STEP_RISK_SCORING,
        request.session_id,
        domain=domain,
    ) as step_output:
        risks_data = session.get("risks_json")
        if risks_data:
            risks = json.loads(risks_data)
        else:
            contract = json.loads(session.get("contract_json") or "{}")
            impact = json.loads(session.get("impact_json") or "{}")
            risks = score_risks(contract, impact, domain)

        trace.emit(
            "Blocked autonomous merge",
            status=TraceStatus.BLOCKED,
            explanation=risks.get("blocked_message"),
        )
        session_store.update_session(request.session_id, risks_json=json.dumps(risks))
        sync_workflow_state(request.session_id, {"risks_scored": True})
        session_store.save_trace(request.session_id)
        step_output["data"] = {
            "autonomous_change_allowed": risks.get("autonomous_change_allowed"),
            "risk_levels": risks.get("risks"),
        }

    flush_traces()
    return RiskAssessment(**risks)


@app.post("/api/tests/generate", response_model=TestGenerateResponse)
def tests_generate(session_id: str | None = None) -> TestGenerateResponse:
    session = _resolve_session(session_id)
    trace = session_store.get_trace(session["id"])
    domain = session.get("domain", "procurement")

    with trace_regshift_step(
        WORKFLOW_STEP_TEST_GENERATION,
        session["id"],
        domain=domain,
    ) as step_output:
        contract = json.loads(session.get("contract_json") or "{}")
        tests = generate_tests(contract, domain, session_id=session["id"])
        trace.emit("Generated contract tests", evidence_count=len(tests))

        session_store.update_session(
            session["id"],
            tests_json=json.dumps([test.model_dump() for test in tests]),
        )
        sync_workflow_state(session["id"], {"tests_generated": True})
        session_store.save_trace(session["id"])
        step_output["data"] = {"test_count": len(tests)}

    flush_traces()
    return TestGenerateResponse(session_id=session["id"], tests=tests, trace=trace.get_events())


@app.post("/api/simulation/run", response_model=SimulationResponse)
def simulation_run(session_id: str | None = None) -> SimulationResponse:
    session = _resolve_session(session_id)
    trace = session_store.get_trace(session["id"])
    domain = session.get("domain", "procurement")

    with trace_regshift_step(
        WORKFLOW_STEP_SIMULATION,
        session["id"],
        domain=domain,
    ) as step_output:
        contract = json.loads(session.get("contract_json") or "{}")
        simulation = run_simulation(contract, domain)
        trace.emit("Ran before/after simulation", explanation=simulation["summary"])

        serializable = {
            "before": [case.model_dump() for case in simulation["before"]],
            "after": [case.model_dump() for case in simulation["after"]],
            "summary": simulation["summary"],
        }
        session_store.update_session(session["id"], simulation_json=json.dumps(serializable))
        sync_workflow_state(session["id"], {"simulation_run": True})
        session_store.save_trace(session["id"])
        step_output["data"] = {
            "summary": simulation["summary"],
            "after_pass_count": sum(1 for case in simulation["after"] if case.verdict == "pass"),
        }

    flush_traces()
    return SimulationResponse(
        session_id=session["id"],
        before=simulation["before"],
        after=simulation["after"],
        summary=simulation["summary"],
        trace=trace.get_events(),
    )


@app.post("/api/pack/generate", response_model=PackResponse)
def pack_generate(request: PackGenerateRequest) -> PackResponse:
    session = _resolve_session(request.session_id)
    trace = session_store.get_trace(request.session_id)
    domain = session.get("domain", "procurement")

    evaluation = evaluate_production_gate(session)
    if not evaluation.passed:
        raise HTTPException(
            status_code=403,
            detail=f"Production gate blocked: {evaluation.summary}. Run governance evaluation first.",
        )

    allowed, reason = validate_action(request.session_id, "pack_generate")
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)

    with trace_regshift_step(
        WORKFLOW_STEP_PACK_GENERATION,
        request.session_id,
        domain=domain,
    ) as step_output:
        session_data = dict(session)
        session_data["impact_json"] = json.loads(session.get("impact_json") or "{}")
        session_data["risks_json"] = json.loads(session.get("risks_json") or "{}")
        session_data["tests_json"] = json.loads(session.get("tests_json") or "[]")
        session_data["simulation_json"] = json.loads(session.get("simulation_json") or "{}")
        session_data["graph_json"] = json.loads(session.get("graph_json") or "{}")

        pack = generate_change_pack(session_data)
        trace.emit("Generated approval pack", explanation=pack["filename"])

        session_store.update_session(
            request.session_id,
            pack_id=pack["pack_id"],
            governance_json=json.dumps(evaluation.model_dump()),
        )
        sync_workflow_state(request.session_id, {"pack_generated": True, "governance_passed": True})
        session_store.save_trace(request.session_id)
        step_output["data"] = {"pack_id": pack["pack_id"], "filename": pack["filename"]}

    flush_traces()

    return PackResponse(
        session_id=request.session_id,
        pack_id=pack["pack_id"],
        filename=pack["filename"],
        markdown=pack["markdown"],
        trace=trace.get_events(),
    )


@app.get("/api/pack/{pack_id}")
def pack_get(pack_id: str) -> dict[str, str]:
    content = read_change_pack(pack_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Pack not found")
    return {"pack_id": pack_id, "markdown": content}


@app.post("/api/pack/load", response_model=PackLoadResponse)
def pack_load(request: PackLoadRequest) -> PackLoadResponse:
    pack_id = request.pack_id.replace(".md", "")
    markdown = read_change_pack(pack_id)
    if markdown is None:
        raise HTTPException(status_code=404, detail=f"Change pack not found: {request.pack_id}")

    filename = f"{pack_id}.md" if not pack_id.endswith(".md") else pack_id
    session = _find_session_by_pack_id(pack_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"No session linked to pack {pack_id}. Re-run the workflow or open from an active session.",
        )

    return PackLoadResponse(
        session_id=session["id"],
        pack_id=pack_id,
        filename=filename,
        markdown=markdown,
        contract_yaml=session.get("contract_yaml"),
        domain=session.get("domain"),
    )


@app.post("/api/implement/apply", response_model=ImplementApplyResponse)
def implement_apply(request: ImplementApplyRequest) -> ImplementApplyResponse:
    session = _resolve_session(request.session_id)
    trace = session_store.get_trace(request.session_id)

    allowed, reason = validate_action(request.session_id, "implement_apply")
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)

    agent_limits = _load_agent_limits(session)
    if not agent_limits.get("can_generate_patch", True):
        raise HTTPException(
            status_code=403,
            detail=agent_limits.get("blocked_message") or "Patch generation blocked by tenant policy",
        )

    pack_id = request.pack_id or session.get("pack_id")
    result = apply_change_contract_to_erpnext(session)

    graph_data = json.loads(session.get("graph_json") or '{"nodes": [], "edges": []}')
    extended = extend_graph_with_implementation(graph_data, result.get("patches", []), pack_id=pack_id)

    neo4j_result = persist_session_graph(
        request.session_id,
        extended["nodes"],
        extended["edges"],
    )
    trace.emit(
        "Applied ERPNext implementation patches",
        explanation=f"{len(result.get('patches', []))} patch(es) written to {result.get('repo_path')}",
        evidence_count=len(result.get("patches", [])),
    )
    trace.emit(
        "Extended knowledge graph with implementation nodes",
        explanation=f"{len(extended['nodes'])} nodes total ({neo4j_result.get('backend', 'session')})",
    )

    session_store.update_session(
        request.session_id,
        graph_json=json.dumps(
            {
                "nodes": [node.model_dump() for node in extended["nodes"]],
                "edges": [edge.model_dump() for edge in extended["edges"]],
            }
        ),
        implementation_json=json.dumps(result),
    )
    sync_workflow_state(request.session_id, {"implementation_applied": True})
    session_store.save_trace(request.session_id)
    flush_traces()

    graph_response = GraphResponse(
        session_id=request.session_id,
        nodes=extended["nodes"],
        edges=extended["edges"],
    )

    return ImplementApplyResponse(
        session_id=request.session_id,
        applied=bool(result.get("applied")),
        reason=result.get("reason"),
        repo_path=str(result.get("repo_path", "")),
        patches=[CodePatchRecord(**patch) for patch in result.get("patches", [])],
        graph=graph_response,
        trace=trace.get_events(),
    )


def _find_session_by_pack_id(pack_id: str) -> dict[str, Any] | None:
    normalized = pack_id.replace(".md", "")
    for session in session_store.list_sessions(limit=200):
        session_pack = session.get("pack_id")
        if session_pack and session_pack.replace(".md", "") == normalized:
            full = session_store.get_session(session["id"])
            if full:
                return full
    return None


def _load_agent_limits(session: dict[str, Any]) -> dict[str, Any]:
    risks_json = session.get("risks_json")
    if isinstance(risks_json, str) and risks_json.strip():
        data = json.loads(risks_json)
        limits = data.get("agent_limits")
        if isinstance(limits, dict):
            return limits
    contract_yaml = session.get("contract_yaml") or ""
    if contract_yaml:
        contract = parse_contract_yaml(contract_yaml)
        limits = contract.get("agent_limits")
        if isinstance(limits, dict):
            return limits
    return {"can_generate_patch": True}


@app.post("/api/stream/workflow/run")
def stream_agent_workflow_run(request: AgentWorkflowStartRequest) -> StreamingResponse:
    from app.orchestration.agent_runner import run_agent_start

    return create_sse_response(lambda: run_agent_start(request.text, request.session_id))


@app.post("/api/stream/workflow/resume")
def stream_agent_workflow_resume(request: AgentWorkflowResumeRequest) -> StreamingResponse:
    from app.orchestration.agent_runner import run_agent_resume

    return create_sse_response(lambda: run_agent_resume(request.session_id))


@app.post("/api/stream/change/classify")
def stream_change_classify(request: ClassifyRequest) -> StreamingResponse:
    return create_sse_response(lambda: change_classify(request))


@app.post("/api/stream/contract/generate")
def stream_contract_generate(request: ContractGenerateRequest) -> StreamingResponse:
    return create_sse_response(lambda: contract_generate(request))


@app.post("/api/stream/contract/approve")
def stream_contract_approve(request: ContractApproveRequest) -> StreamingResponse:
    return create_sse_response(lambda: contract_approve(request))


@app.post("/api/stream/impact/analyze")
def stream_impact_analyze(request: ImpactAnalyzeRequest) -> StreamingResponse:
    return create_sse_response(lambda: impact_analyze(request))


@app.post("/api/stream/risk/score")
def stream_risk_score(request: RiskScoreRequest) -> StreamingResponse:
    def handler() -> RiskScoreResponse:
        assessment = risk_score(request)
        trace = session_store.get_trace(request.session_id).get_events()
        return RiskScoreResponse(
            session_id=request.session_id,
            assessment=assessment,
            trace=trace,
        )

    return create_sse_response(handler)


@app.post("/api/stream/tests/generate")
def stream_tests_generate(session_id: str | None = None) -> StreamingResponse:
    return create_sse_response(lambda: tests_generate(session_id))


@app.post("/api/stream/simulation/run")
def stream_simulation_run(session_id: str | None = None) -> StreamingResponse:
    return create_sse_response(lambda: simulation_run(session_id))


@app.get("/api/stream/governance/evaluate")
def stream_governance_evaluate(session_id: str) -> StreamingResponse:
    def handler() -> GovernanceEvaluateResponse:
        evaluation = governance_evaluate(session_id)
        orchestration = orchestration_status(session_id)
        trace = session_store.get_trace(session_id).get_events()
        return GovernanceEvaluateResponse(
            session_id=session_id,
            evaluation=evaluation,
            orchestration=orchestration,
            trace=trace,
        )

    return create_sse_response(handler)


@app.post("/api/stream/pack/generate")
def stream_pack_generate(request: PackGenerateRequest) -> StreamingResponse:
    return create_sse_response(lambda: pack_generate(request))

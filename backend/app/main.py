import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, session_store
from app.models.schemas import (
    AgentTraceEvent,
    ClassifyRequest,
    ClassifyResponse,
    ContractApproveRequest,
    ContractGenerateRequest,
    ContractResponse,
    DomainAlternative,
    GovernanceConfigResponse,
    GovernanceEvaluation,
    GraphResponse,
    HealthResponse,
    ImpactAnalyzeRequest,
    ImpactResponse,
    IndexStatusResponse,
    OrchestrationStatusResponse,
    PackGenerateRequest,
    PackResponse,
    PolicyIngestRequest,
    PolicyIngestResponse,
    PolicyListResponse,
    PolicyDocument,
    PolicyRule,
    RiskAssessment,
    RiskScoreRequest,
    SimulationResponse,
    TestGenerateResponse,
    TraceStatus,
)
from app.orchestration.workflow import get_workflow_status, init_workflow_state, sync_workflow_state, validate_action
from app.services.classifier import classify_change
from app.services.contract_compiler import compile_contract, parse_contract_yaml
from app.services.graph_builder import build_graph
from app.services.impact_analyzer import analyze_impact
from app.services.neo4j_store import load_session_graph, neo4j_status, persist_session_graph, trace_obligation_path
from app.services.pack_generator import generate_change_pack, read_change_pack
from app.services.policy_governance import evaluate_production_gate
from app.services.policy_compiler import build_governance_config
from app.services.policy_ingestor import ingest_policy_document
from app.services.policy_seed import seed_demo_policies
from app.services.policy_store import get_active_policy, ingest_policy, list_policies
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
    trace_nested_step,
    trace_policy_extraction,
    trace_regshift_step,
)
from app.services.workflow_trace import build_workflow_trace_summary
from app.services.policy_graph import (
    extract_workflow_guidance,
    get_policy_graph_visualization,
    persist_policy_knowledge_graph,
)
from app.services.risk_engine import score_risks
from app.services.scanner import get_index_status, scan_index
from app.services.simulator import run_simulation
from app.services.test_generator import generate_tests

app = FastAPI(title="RegShift API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    settings_paths()
    try:
        status = get_index_status()
        if status["file_count"] == 0:
            scan_index("procurement")
    except Exception:
        pass
    try:
        seed_demo_policies()
    except Exception:
        pass


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


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="regshift-backend",
        neo4j=neo4j_status(),
        langfuse=langfuse_status(),
        orchestration="langgraph",
    )


@app.get("/api/index/status", response_model=IndexStatusResponse)
def index_status() -> IndexStatusResponse:
    status = get_index_status()
    return IndexStatusResponse(**status)


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
def policy_graph(domain: str) -> dict[str, Any]:
    return get_policy_graph_visualization(domain)


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

        result = classify_change(request.text)
        trace.emit(
            f"Classified domain as {result['domain']}",
            explanation=f"Confidence {result['confidence']}",
            evidence_count=len(result.get("alternatives", [])) + 1,
        )

        session_store.update_session(session_id, domain=result["domain"], business_text=request.text)
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
        trace=trace.get_events(),
    )


@app.post("/api/contract/generate", response_model=ContractResponse)
def contract_generate(request: ContractGenerateRequest) -> ContractResponse:
    session_id = request.session_id
    if not session_id:
        session_id = session_store.create_session(request.text)

    session = _resolve_session(session_id)
    trace = session_store.get_trace(session_id)

    domain = request.domain or session.get("domain") or classify_change(request.text)["domain"]
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

        compiled = compile_contract(request.text, domain)
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
        trace.emit("Queried Conduct-style system context", explanation="ERPNext indexed context loaded")

        with trace_nested_step(WORKFLOW_STEP_INDEX_SCAN) as index_output:
            trace.emit("Scanned ERPNext code index", explanation="Ranking impacted files")
            index_output["data"] = {"indexed": True}

        with trace_nested_step("analyze_impact") as impact_output:
            impact = analyze_impact(contract, domain)
            impact_output["data"] = {"file_count": len(impact["files"]), "modules": impact["modules"]}

        trace.emit(
            "Ranked impacted files",
            evidence_count=len(impact["files"]),
            explanation="Evidence snippets attached to top matches",
        )

        with trace_nested_step(WORKFLOW_STEP_TEST_GENERATION) as tests_output:
            tests = [test.model_dump() for test in generate_tests(contract, domain)]
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
        tests = generate_tests(contract, domain)
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

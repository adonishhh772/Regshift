from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TraceStatus(StrEnum):
    COMPLETED = "completed"
    ACTIVE = "active"
    BLOCKED = "blocked"
    PENDING = "pending"
    ERROR = "error"


class AgentTraceEvent(BaseModel):
    timestamp: str
    message: str
    status: TraceStatus
    explanation: str | None = None
    evidence_count: int | None = None


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=10)
    session_id: str | None = None


class AgentWorkflowStartRequest(BaseModel):
    text: str = Field(min_length=10)
    session_id: str | None = None


class AgentWorkflowResumeRequest(BaseModel):
    session_id: str


class AgentWorkflowResult(BaseModel):
    session_id: str
    status: str
    pause_gate: str | None = None
    summary: str
    domain: str | None = None
    confidence: float | None = None
    contract_yaml: str | None = None
    contract_approved: bool = False
    pack_filename: str | None = None
    pack_markdown: str | None = None
    governance_passed: bool | None = None
    processes: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)
    impacted_file_count: int = 0
    graph_node_count: int = 0
    graph_edge_count: int = 0
    tests_count: int = 0
    simulation_summary: str | None = None
    autonomous_change_allowed: bool | None = None
    trace: list[AgentTraceEvent] = Field(default_factory=list)


class DomainAlternative(BaseModel):
    domain: str
    score: float


class ClassifyResponse(BaseModel):
    session_id: str
    domain: str
    confidence: float
    alternatives: list[DomainAlternative] = Field(default_factory=list)
    systems: "SystemIdentification | None" = None
    trace: list[AgentTraceEvent] = Field(default_factory=list)


class IdentifiedSystem(BaseModel):
    system_id: str
    name: str
    vendor: str
    confidence: float
    role: str
    ingested: bool = False
    matched_signals: list[str] = Field(default_factory=list)


class SystemIdentification(BaseModel):
    primary_system_id: str | None = None
    systems: list[IdentifiedSystem] = Field(default_factory=list)
    needs_confirmation: bool = False
    confirmed: bool = False


class SystemConfirmRequest(BaseModel):
    session_id: str
    system_ids: list[str] = Field(min_length=1)


class SystemSummary(BaseModel):
    id: str
    name: str
    vendor: str
    connector: str
    domains: list[str] = Field(default_factory=list)
    source_type: str
    source_path: str | None = None
    source_available: bool = False
    ingest_status: str | None = None
    file_count: int = 0
    node_count: int = 0
    edge_count: int = 0
    last_ingest: str | None = None


class SystemListResponse(BaseModel):
    systems: list[SystemSummary] = Field(default_factory=list)
    total: int = 0


class SystemIngestResponse(BaseModel):
    system_id: str
    persisted: bool
    status: str
    reason: str | None = None
    backend: str | None = None
    node_count: int = 0
    edge_count: int = 0
    file_count: int = 0
    last_ingest: str | None = None


class SystemIngestAllResponse(BaseModel):
    total: int
    succeeded: int
    results: list[SystemIngestResponse] = Field(default_factory=list)



class ContractGenerateRequest(BaseModel):
    text: str = Field(min_length=10)
    domain: str | None = None
    session_id: str | None = None


class ContractApproveRequest(BaseModel):
    session_id: str
    contract_yaml: str


class ContractResponse(BaseModel):
    session_id: str
    domain: str
    contract_yaml: str
    contract: dict[str, Any]
    approved: bool = False
    confidence: str = "deterministic"
    trace: list[AgentTraceEvent] = Field(default_factory=list)


class IndexStatusResponse(BaseModel):
    status: str
    file_count: int
    source: str
    last_scan: str | None = None


class ImpactAnalyzeRequest(BaseModel):
    session_id: str


class ImpactedFile(BaseModel):
    path: str
    module: str
    score: float
    evidence_snippet: str
    keywords: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)


class ImpactResponse(BaseModel):
    session_id: str
    processes: list[str]
    modules: list[str]
    files: list[ImpactedFile]
    trace: list[AgentTraceEvent] = Field(default_factory=list)


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    status: str = "completed"
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    type: str


class GraphResponse(BaseModel):
    session_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class SystemGraphResponse(BaseModel):
    system_id: str | None = None
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class RiskScoreRequest(BaseModel):
    session_id: str


class RiskAssessment(BaseModel):
    risks: dict[str, str]
    agent_limits: dict[str, bool | str]
    blocked_message: str
    autonomous_change_allowed: bool = False
    policy_source: dict[str, Any] | None = None


class RiskScoreResponse(BaseModel):
    session_id: str
    assessment: RiskAssessment
    trace: list[AgentTraceEvent] = Field(default_factory=list)


class GeneratedTest(BaseModel):
    id: str
    name: str
    description: str
    contract_rule: str
    pytest_code: str


class TestGenerateResponse(BaseModel):
    session_id: str
    tests: list[GeneratedTest]
    trace: list[AgentTraceEvent] = Field(default_factory=list)


class SimulationCase(BaseModel):
    label: str
    amount: float
    approval: str
    result: str
    verdict: str


class SimulationResponse(BaseModel):
    session_id: str
    before: list[SimulationCase]
    after: list[SimulationCase]
    summary: str
    trace: list[AgentTraceEvent] = Field(default_factory=list)


class PackGenerateRequest(BaseModel):
    session_id: str


class PackResponse(BaseModel):
    session_id: str
    pack_id: str
    filename: str
    markdown: str
    trace: list[AgentTraceEvent] = Field(default_factory=list)


class PackLoadRequest(BaseModel):
    pack_id: str = Field(min_length=8)


class PackLoadResponse(BaseModel):
    session_id: str
    pack_id: str
    filename: str
    markdown: str
    contract_yaml: str | None = None
    domain: str | None = None


class CodePatchRecord(BaseModel):
    patch_id: str
    file_path: str
    obligation: str
    change_type: str
    description: str
    lines_added: int


class ImplementApplyRequest(BaseModel):
    session_id: str
    pack_id: str | None = None


class ImplementApplyResponse(BaseModel):
    session_id: str
    applied: bool
    reason: str | None = None
    repo_path: str
    patches: list[CodePatchRecord] = Field(default_factory=list)
    graph: GraphResponse | None = None
    trace: list[AgentTraceEvent] = Field(default_factory=list)


class SessionResponse(BaseModel):
    session_id: str
    business_text: str
    domain: str
    contract_yaml: str | None
    contract_approved: bool
    trace: list[AgentTraceEvent]


class GovernanceCheck(BaseModel):
    id: str
    name: str
    passed: bool
    severity: str
    explanation: str


class GovernanceEvaluation(BaseModel):
    gate_status: str
    passed: bool
    checks: list[GovernanceCheck]
    summary: str
    agent_limits: dict[str, bool | str]
    blocked_message: str
    evaluation_trace_id: str


class OrchestrationStatusResponse(BaseModel):
    session_id: str
    current_step: str
    gate_status: str
    blocked_reason: str | None = None
    contract_approved: bool = False
    governance_passed: bool = False
    graph_backend: str = "networkx_fallback"


class GovernanceEvaluateResponse(BaseModel):
    session_id: str
    evaluation: GovernanceEvaluation
    orchestration: OrchestrationStatusResponse
    trace: list[AgentTraceEvent] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    service: str
    neo4j: dict[str, Any]
    langfuse: dict[str, Any] = Field(default_factory=dict)
    llm: dict[str, Any] = Field(default_factory=dict)
    orchestration: str = "langgraph"


class PolicyRule(BaseModel):
    id: str
    type: str
    value: str | int | bool | None = None
    key: str | None = None
    citation: str
    description: str


class PolicyIngestRequest(BaseModel):
    title: str = Field(min_length=3)
    source_text: str = Field(min_length=20)
    domain: str | None = None


class PolicyDocument(BaseModel):
    id: str
    tenant_id: str
    title: str
    domain: str | None
    source_text: str
    version: int
    status: str
    rules: dict[str, Any]
    created_at: str
    updated_at: str


class PolicyIngestResponse(BaseModel):
    policy: PolicyDocument
    extracted_rules: list[PolicyRule]
    rule_count: int
    trace: list[AgentTraceEvent] = Field(default_factory=list)


class PolicyListResponse(BaseModel):
    policies: list[PolicyDocument]
    active_domains: list[str]


class PolicyActivateResponse(BaseModel):
    policy: PolicyDocument
    graph_backend: str | None = None
    node_count: int = 0


class GovernanceConfigResponse(BaseModel):
    domain: str
    configured: bool
    policy_id: str | None = None
    policy_title: str | None = None
    policy_version: int | None = None
    obligations: list[str] = Field(default_factory=list)
    threshold: int | None = None
    approval_roles: list[str] = Field(default_factory=list)
    agent_limits: dict[str, bool | str] = Field(default_factory=dict)
    citations: dict[str, str] = Field(default_factory=dict)


class SessionSummary(BaseModel):
    id: str
    business_text: str
    domain: str | None = None
    contract_approved: bool = False
    has_contract: bool = False
    pack_id: str | None = None
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary] = Field(default_factory=list)
    total: int = 0


class SessionDetailResponse(BaseModel):
    id: str
    business_text: str
    domain: str | None = None
    contract_yaml: str | None = None
    contract: dict[str, Any] | None = None
    contract_approved: bool = False
    pack_id: str | None = None
    created_at: str
    updated_at: str


class DomainPackSummary(BaseModel):
    domain: str
    display_name: str
    description: str
    process_count: int = 0
    module_count: int = 0


class DomainPackListResponse(BaseModel):
    packs: list[DomainPackSummary] = Field(default_factory=list)


class DashboardDomainCount(BaseModel):
    domain: str
    count: int


class DashboardStatsResponse(BaseModel):
    total_sessions: int = 0
    sessions_with_contracts: int = 0
    approved_contracts: int = 0
    change_packs: int = 0
    indexed_files: int = 0
    index_source: str = "unknown"
    active_policies: int = 0
    domain_packs: int = 0
    sessions_by_domain: list[DashboardDomainCount] = Field(default_factory=list)
    graph_backend: str = "networkx_fallback"
    backend_status: str = "ok"

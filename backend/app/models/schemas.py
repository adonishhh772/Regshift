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


class DomainAlternative(BaseModel):
    domain: str
    score: float


class ClassifyResponse(BaseModel):
    session_id: str
    domain: str
    confidence: float
    alternatives: list[DomainAlternative] = Field(default_factory=list)
    trace: list[AgentTraceEvent] = Field(default_factory=list)


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


class RiskScoreRequest(BaseModel):
    session_id: str


class RiskAssessment(BaseModel):
    risks: dict[str, str]
    agent_limits: dict[str, bool | str]
    blocked_message: str
    autonomous_change_allowed: bool = False
    policy_source: dict[str, Any] | None = None


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

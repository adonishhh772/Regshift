export type TraceStatus = "completed" | "active" | "blocked" | "pending" | "error";

export interface AgentTraceEvent {
  timestamp: string;
  message: string;
  status: TraceStatus;
  explanation?: string | null;
  evidence_count?: number | null;
}

export interface AgentWorkflowResult {
  session_id: string;
  status: "completed" | "paused" | "blocked";
  pause_gate?: string | null;
  summary: string;
  domain?: string | null;
  confidence?: number | null;
  contract_yaml?: string | null;
  contract_approved: boolean;
  pack_filename?: string | null;
  pack_markdown?: string | null;
  governance_passed?: boolean | null;
  processes: string[];
  modules: string[];
  impacted_file_count: number;
  graph_node_count: number;
  graph_edge_count: number;
  tests_count: number;
  simulation_summary?: string | null;
  autonomous_change_allowed?: boolean | null;
  trace: AgentTraceEvent[];
}

export interface IdentifiedSystem {
  system_id: string;
  name: string;
  vendor: string;
  confidence: number;
  role: string;
  ingested: boolean;
  matched_signals: string[];
}

export interface SystemIdentification {
  primary_system_id: string | null;
  systems: IdentifiedSystem[];
  needs_confirmation: boolean;
  confirmed: boolean;
}

export interface SystemSummary {
  id: string;
  name: string;
  vendor: string;
  connector: string;
  domains: string[];
  source_type: string;
  source_path: string | null;
  source_available: boolean;
  ingest_status: string | null;
  file_count: number;
  node_count: number;
  edge_count: number;
  last_ingest: string | null;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  status: string;
  metadata: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  type: string;
}

export interface CodePatchRecord {
  patch_id: string;
  file_path: string;
  obligation: string;
  change_type: string;
  description: string;
  lines_added: number;
}

export interface ImplementApplyResponse {
  session_id: string;
  applied: boolean;
  reason?: string | null;
  repo_path: string;
  patches: CodePatchRecord[];
  graph?: {
    session_id: string;
    nodes: GraphNode[];
    edges: GraphEdge[];
  } | null;
  trace: AgentTraceEvent[];
}

export interface ImpactedFile {
  path: string;
  module: string;
  score: number;
  evidence_snippet: string;
  keywords: string[];
  symbols: string[];
}

export interface GeneratedTest {
  id: string;
  name: string;
  description: string;
  contract_rule: string;
  pytest_code: string;
}

export interface SimulationCase {
  label: string;
  amount: number;
  approval: string;
  result: string;
  verdict: string;
}

export interface RiskAssessment {
  risks: Record<string, string>;
  agent_limits: Record<string, boolean | string>;
  blocked_message: string;
  autonomous_change_allowed: boolean;
}

export type WorkflowStepId =
  | "intake"
  | "contract"
  | "graph"
  | "impact"
  | "risk"
  | "tests"
  | "simulation"
  | "pack";

export type StepStatus = "pending" | "active" | "approved" | "blocked" | "completed";

export interface WorkflowStep {
  id: WorkflowStepId;
  label: string;
  status: StepStatus;
}

export interface IndexStatus {
  status: string;
  file_count: number;
  source: string;
  last_scan: string | null;
}

export interface GovernanceCheck {
  id: string;
  name: string;
  passed: boolean;
  severity: string;
  explanation: string;
}

export interface GovernanceEvaluation {
  gate_status: string;
  passed: boolean;
  checks: GovernanceCheck[];
  summary: string;
  agent_limits: Record<string, boolean | string>;
  blocked_message: string;
  evaluation_trace_id: string;
}

export interface OrchestrationStatus {
  session_id: string;
  current_step: string;
  gate_status: string;
  blocked_reason: string | null;
  contract_approved: boolean;
  governance_passed: boolean;
  graph_backend: string;
}

export interface HealthStatus {
  status: string;
  service: string;
  neo4j: { available: boolean; backend: string };
  langfuse?: {
    available: boolean;
    enabled: boolean;
    authenticated?: boolean;
    ui_url?: string;
    project_id?: string;
    auth_error?: string;
  };
  orchestration: string;
}

export interface PolicyGraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  backend: string;
  policy_id?: string | null;
  policy_title?: string | null;
  policy_version?: number | null;
  domain?: string | null;
}

export interface WorkflowGuidance {
  configured: boolean;
  domain: string;
  policy_id?: string;
  policy_title?: string;
  required_obligations?: string[];
  threshold?: number | null;
  approval_roles?: string[];
  required_steps?: string[];
  blocked_actions?: string[];
  message?: string;
  source?: string;
}

export interface WorkflowTraceStep {
  id: string;
  status: string;
  api_action?: string | null;
}

export interface WorkflowTraceSummary {
  session_id: string;
  current_step: string;
  gate_status: string;
  blocked_reason?: string | null;
  steps: WorkflowTraceStep[];
  all_steps: string[];
  langfuse: {
    available: boolean;
    enabled: boolean;
    ui_url?: string;
    session_trace_url?: string | null;
  };
}

export interface PolicyRule {
  id: string;
  type: string;
  value?: string | number | boolean | null;
  key?: string | null;
  citation: string;
  description: string;
}

export interface PolicyDocument {
  id: string;
  tenant_id: string;
  title: string;
  domain: string | null;
  source_text: string;
  version: number;
  status: string;
  rules: Record<string, unknown> & {
    obligations?: string[];
    threshold?: number;
    approval_roles?: string[];
    agent_limits?: Record<string, boolean>;
    rules?: PolicyRule[];
    rule_count?: number;
  };
  created_at: string;
  updated_at: string;
}

export interface PolicyIngestResponse {
  policy: PolicyDocument;
  extracted_rules: PolicyRule[];
  rule_count: number;
  trace: AgentTraceEvent[];
}

export interface GovernanceConfig {
  domain: string;
  configured: boolean;
  policy_id?: string | null;
  policy_title?: string | null;
  policy_version?: number | null;
  obligations: string[];
  threshold?: number | null;
  approval_roles: string[];
  agent_limits: Record<string, boolean | string>;
  citations: Record<string, string>;
}

export type ChatMessageRole = "user" | "assistant" | "system";

export interface ThinkingStep {
  id: string;
  action: string;
  status: TraceStatus;
  resultTag?: string;
  description?: string;
}

export interface ChatThinkingBlock {
  headline: string;
  steps: ThinkingStep[];
  isStreaming: boolean;
  subagentsExpanded: boolean;
  toolCallCount: number;
}

export interface ChatContractApprovalBlock {
  contractYaml: string;
  domain: string | null;
  approved: boolean;
}

export interface ChatMessage {
  id: string;
  role: ChatMessageRole;
  content: string;
  timestamp: string;
  status?: TraceStatus;
  thinking?: ChatThinkingBlock;
  contractApproval?: ChatContractApprovalBlock;
}

export type BackendConnectionStatus = "checking" | "online" | "offline";

export interface SessionSummary {
  id: string;
  business_text: string;
  domain: string | null;
  contract_approved: boolean;
  has_contract: boolean;
  pack_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
  total: number;
}

export interface SessionDetail {
  id: string;
  business_text: string;
  domain: string | null;
  contract_yaml: string | null;
  contract: Record<string, unknown> | null;
  contract_approved: boolean;
  pack_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface DomainPackSummary {
  domain: string;
  display_name: string;
  description: string;
  process_count: number;
  module_count: number;
}

export interface DomainPackListResponse {
  packs: DomainPackSummary[];
}

export interface DashboardDomainCount {
  domain: string;
  count: number;
}

export interface DashboardStats {
  total_sessions: number;
  sessions_with_contracts: number;
  approved_contracts: number;
  change_packs: number;
  indexed_files: number;
  index_source: string;
  active_policies: number;
  domain_packs: number;
  sessions_by_domain: DashboardDomainCount[];
  graph_backend: string;
  backend_status: string;
}

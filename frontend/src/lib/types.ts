export type TraceStatus = "completed" | "active" | "blocked" | "pending" | "error";

export interface AgentTraceEvent {
  timestamp: string;
  message: string;
  status: TraceStatus;
  explanation?: string | null;
  evidence_count?: number | null;
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
  langfuse?: { available: boolean; enabled: boolean; ui_url?: string };
  orchestration: string;
}

export interface PolicyGraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  backend: string;
  policy_id?: string;
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

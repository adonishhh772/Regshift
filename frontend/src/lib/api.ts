import { parseApiErrorMessage } from "./apiErrors";
import { fetchWithTimeout } from "./fetchWithTimeout";
import { normalizeFetchError } from "./networkErrors";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const HEALTH_LIVE_TIMEOUT_MS = 5_000;
const HEALTH_TIMEOUT_MS = 10_000;
const API_TIMEOUT_MS = 15_000;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetchWithTimeout(
      `${API_BASE}${path}`,
      {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(options?.headers ?? {}),
        },
      },
      API_TIMEOUT_MS
    );

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(parseApiErrorMessage(detail || `Request failed: ${response.status}`));
    }

    return response.json() as Promise<T>;
  } catch (error) {
    throw new Error(normalizeFetchError(error));
  }
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  indexStatus: () => request<import("./types").IndexStatus>("/api/index/status"),
  scanIndex: () => request<import("./types").IndexStatus>("/api/index/scan", { method: "POST" }),
  classify: (text: string, sessionId?: string) =>
    request<{
      session_id: string;
      domain: string;
      confidence: number;
      systems: import("./types").SystemIdentification | null;
      trace: import("./types").AgentTraceEvent[];
    }>("/api/change/classify", { method: "POST", body: JSON.stringify({ text, session_id: sessionId }) }),
  listSystems: () =>
    request<{ systems: import("./types").SystemSummary[]; total: number }>("/api/systems"),
  ingestSystems: () =>
    request<{ total: number; succeeded: number }>("/api/systems/ingest", { method: "POST" }),
  ingestSystem: (systemId: string) =>
    request<{
      system_id: string;
      persisted: boolean;
      status: string;
      node_count?: number;
      file_count?: number;
      reason?: string;
    }>(`/api/systems/${encodeURIComponent(systemId)}/ingest`, { method: "POST" }),
  confirmSystems: (sessionId: string, systemIds: string[]) =>
    request<import("./types").SystemIdentification>("/api/systems/confirm", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, system_ids: systemIds }),
    }),
  getSystemGraph: (systemId?: string) =>
    request<{ system_id: string | null; nodes: import("./types").GraphNode[]; edges: import("./types").GraphEdge[] }>(
      `/api/systems/graph${systemId ? `?system_id=${encodeURIComponent(systemId)}` : ""}`
    ),
  generateContract: (text: string, domain?: string, sessionId?: string) =>
    request<{
      session_id: string;
      domain: string;
      contract_yaml: string;
      contract: Record<string, unknown>;
      approved: boolean;
      trace: import("./types").AgentTraceEvent[];
    }>("/api/contract/generate", {
      method: "POST",
      body: JSON.stringify({ text, domain, session_id: sessionId }),
    }),
  approveContract: (sessionId: string, contractYaml: string) =>
    request<{
      session_id: string;
      domain: string;
      contract_yaml: string;
      approved: boolean;
      trace: import("./types").AgentTraceEvent[];
    }>("/api/contract/approve", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, contract_yaml: contractYaml }),
    }),
  analyzeImpact: (sessionId: string) =>
    request<{
      session_id: string;
      processes: string[];
      modules: string[];
      files: import("./types").ImpactedFile[];
      trace: import("./types").AgentTraceEvent[];
    }>("/api/impact/analyze", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    }),
  getGraph: (sessionId?: string) =>
    request<{ session_id: string; nodes: import("./types").GraphNode[]; edges: import("./types").GraphEdge[] }>(
      `/api/graph/current${sessionId ? `?session_id=${sessionId}` : ""}`
    ),
  scoreRisk: (sessionId: string) =>
    request<import("./types").RiskAssessment>("/api/risk/score", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    }),
  generateTests: (sessionId?: string) =>
    request<{ session_id: string; tests: import("./types").GeneratedTest[]; trace: import("./types").AgentTraceEvent[] }>(
      `/api/tests/generate${sessionId ? `?session_id=${sessionId}` : ""}`,
      { method: "POST" }
    ),
  runSimulation: (sessionId?: string) =>
    request<{
      session_id: string;
      before: import("./types").SimulationCase[];
      after: import("./types").SimulationCase[];
      summary: string;
      trace: import("./types").AgentTraceEvent[];
    }>(`/api/simulation/run${sessionId ? `?session_id=${sessionId}` : ""}`, { method: "POST" }),
  generatePack: (sessionId: string) =>
    request<{
      session_id: string;
      pack_id: string;
      filename: string;
      markdown: string;
      trace: import("./types").AgentTraceEvent[];
    }>("/api/pack/generate", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    }),
  evaluateGovernance: (sessionId: string) =>
    request<import("./types").GovernanceEvaluation>(`/api/governance/evaluate?session_id=${sessionId}`),
  getOrchestrationStatus: (sessionId: string) =>
    request<import("./types").OrchestrationStatus>(`/api/orchestration/status?session_id=${sessionId}`),
  getHealthLive: async () => {
    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/health/live`,
        { headers: { Accept: "application/json" } },
        HEALTH_LIVE_TIMEOUT_MS
      );
      if (!response.ok) {
        throw new Error(`Health check failed: ${response.status}`);
      }
      return response.json() as Promise<{ status: string }>;
    } catch (error) {
      throw new Error(normalizeFetchError(error));
    }
  },
  getHealth: async () => {
    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/health`,
        { headers: { Accept: "application/json" } },
        HEALTH_TIMEOUT_MS
      );
      if (!response.ok) {
        throw new Error(`Health check failed: ${response.status}`);
      }
      return response.json() as Promise<import("./types").HealthStatus>;
    } catch (error) {
      throw new Error(normalizeFetchError(error));
    }
  },
  refreshLangfuse: () =>
    request<{ langfuse: import("./types").HealthStatus["langfuse"]; authenticated: boolean; reason?: string }>(
      "/api/langfuse/refresh",
      { method: "POST" }
    ),
  traceGraphPath: (sessionId: string, obligationNodeId: string) =>
    request<{ path: string[] }>(`/api/graph/trace/${obligationNodeId}?session_id=${sessionId}`),
  ingestPolicy: (payload: { title: string; source_text: string; domain?: string }) =>
    request<import("./types").PolicyIngestResponse>("/api/policy/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listPolicies: () => request<{ policies: import("./types").PolicyDocument[]; active_domains: string[] }>("/api/policy/list"),
  getPolicy: (policyId: string) => request<import("./types").PolicyDocument>(`/api/policy/${policyId}`),
  activatePolicy: (policyId: string) =>
    request<{ policy: import("./types").PolicyDocument; graph_backend: string | null; node_count: number }>(
      `/api/policy/${policyId}/activate`,
      { method: "POST" }
    ),
  getActivePolicy: (domain: string) =>
    request<import("./types").PolicyDocument>(`/api/policy/active/${domain}`),
  getPolicyGovernance: (domain: string) =>
    request<import("./types").GovernanceConfig>(`/api/policy/governance/${domain}`),
  getPolicyGraph: (domain: string, policyId?: string | null) => {
    const query = policyId ? `?policy_id=${encodeURIComponent(policyId)}` : "";
    return request<import("./types").PolicyGraphResponse>(`/api/policy/graph/${domain}${query}`);
  },
  rebuildPolicyGraph: (domain: string) =>
    request<{ persisted: boolean; backend: string; node_count: number; edge_count?: number }>(
      `/api/policy/rebuild-graph/${domain}`,
      { method: "POST" }
    ),
  getWorkflowGuidance: (domain: string) =>
    request<import("./types").WorkflowGuidance>(`/api/policy/workflow-guidance/${domain}`),
  getWorkflowTrace: (sessionId: string) =>
    request<import("./types").WorkflowTraceSummary>(`/api/traces/workflow/${sessionId}`),
  listSessions: () => request<import("./types").SessionListResponse>("/api/sessions"),
  getSession: (sessionId: string) =>
    request<import("./types").SessionDetail>(`/api/sessions/${encodeURIComponent(sessionId)}`),
  listDomainPacks: () => request<import("./types").DomainPackListResponse>("/api/domain-packs"),
  getDashboardStats: () => request<import("./types").DashboardStats>("/api/dashboard/stats"),
  loadPack: (packId: string) =>
    request<{
      session_id: string;
      pack_id: string;
      filename: string;
      markdown: string;
      contract_yaml?: string | null;
      domain?: string | null;
    }>("/api/pack/load", {
      method: "POST",
      body: JSON.stringify({ pack_id: packId }),
    }),
  applyImplementation: (sessionId: string, packId?: string) =>
    request<import("./types").ImplementApplyResponse>("/api/implement/apply", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, pack_id: packId }),
    }),
};

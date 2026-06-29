const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  indexStatus: () => request<import("./types").IndexStatus>("/api/index/status"),
  scanIndex: () => request<import("./types").IndexStatus>("/api/index/scan", { method: "POST" }),
  classify: (text: string, sessionId?: string) =>
    request<{ session_id: string; domain: string; confidence: number; trace: import("./types").AgentTraceEvent[] }>(
      "/api/change/classify",
      { method: "POST", body: JSON.stringify({ text, session_id: sessionId }) }
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
  getHealth: () => request<import("./types").HealthStatus>("/health"),
  traceGraphPath: (sessionId: string, obligationNodeId: string) =>
    request<{ path: string[] }>(`/api/graph/trace/${obligationNodeId}?session_id=${sessionId}`),
  ingestPolicy: (payload: { title: string; source_text: string; domain?: string }) =>
    request<import("./types").PolicyIngestResponse>("/api/policy/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listPolicies: () => request<{ policies: import("./types").PolicyDocument[]; active_domains: string[] }>("/api/policy/list"),
  getActivePolicy: (domain: string) =>
    request<import("./types").PolicyDocument>(`/api/policy/active/${domain}`),
  getPolicyGovernance: (domain: string) =>
    request<import("./types").GovernanceConfig>(`/api/policy/governance/${domain}`),
  getPolicyGraph: (domain: string) =>
    request<import("./types").PolicyGraphResponse>(`/api/policy/graph/${domain}`),
  getWorkflowGuidance: (domain: string) =>
    request<import("./types").WorkflowGuidance>(`/api/policy/workflow-guidance/${domain}`),
  getWorkflowTrace: (sessionId: string) =>
    request<import("./types").WorkflowTraceSummary>(`/api/traces/workflow/${sessionId}`),
};

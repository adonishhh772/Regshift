import type { AgentTraceEvent } from "./types";
import { parseApiErrorMessage } from "./apiErrors";
import { fetchWithTimeout } from "./fetchWithTimeout";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STREAM_TIMEOUT_MS = 300_000;

export interface StreamWorkflowOptions {
  path: string;
  method?: "GET" | "POST";
  body?: unknown;
  onTrace: (event: AgentTraceEvent) => void;
}

function parseSseChunk(chunk: string): Array<{ event: string; data: string }> {
  const messages: Array<{ event: string; data: string }> = [];
  const blocks = chunk.split("\n\n");

  for (const block of blocks) {
    if (!block.trim()) {
      continue;
    }

    const lines = block.split("\n");
    let eventName = "message";
    let dataPayload = "";

    for (const line of lines) {
      if (line.startsWith("event:")) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataPayload = line.slice(5).trim();
      }
    }

    if (dataPayload) {
      messages.push({ event: eventName, data: dataPayload });
    }
  }

  return messages;
}

export async function streamWorkflowRequest<T>(options: StreamWorkflowOptions): Promise<T> {
  const { path, method = "POST", body, onTrace } = options;
  const headers: Record<string, string> = {
    Accept: "text/event-stream",
  };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetchWithTimeout(
    `${API_BASE}${path}`,
    {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    },
    STREAM_TIMEOUT_MS
  );

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(parseApiErrorMessage(detail || `Stream request failed: ${response.status}`));
  }

  if (!response.body) {
    throw new Error("Streaming response body is empty");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let result: T | null = null;

  const processMessages = (messages: Array<{ event: string; data: string }>) => {
    for (const message of messages) {
      const parsed = JSON.parse(message.data) as unknown;

      if (message.event === "trace") {
        onTrace(parsed as AgentTraceEvent);
        continue;
      }

      if (message.event === "result") {
        result = parsed as T;
        continue;
      }

      if (message.event === "error") {
        const errorPayload = parsed as { detail?: string | unknown; status_code?: number };
        const rawDetail =
          typeof errorPayload.detail === "string"
            ? errorPayload.detail
            : JSON.stringify(errorPayload.detail ?? errorPayload);
        throw new Error(parseApiErrorMessage(rawDetail));
      }
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";

    for (const part of parts) {
      if (!part.trim()) {
        continue;
      }
      processMessages(parseSseChunk(`${part}\n\n`));
    }
  }

  if (buffer.trim()) {
    processMessages(parseSseChunk(`${buffer}\n\n`));
  }

  if (result === null) {
    throw new Error("Workflow stream ended without a result");
  }

  return result;
}

export const streamApi = {
  classify: (text: string, sessionId: string | undefined, onTrace: (event: AgentTraceEvent) => void) =>
    streamWorkflowRequest<{
      session_id: string;
      domain: string;
      confidence: number;
      trace: AgentTraceEvent[];
    }>({
      path: "/api/stream/change/classify",
      body: { text, session_id: sessionId },
      onTrace,
    }),

  generateContract: (
    text: string,
    domain: string | undefined,
    sessionId: string | undefined,
    onTrace: (event: AgentTraceEvent) => void
  ) =>
    streamWorkflowRequest<{
      session_id: string;
      domain: string;
      contract_yaml: string;
      contract: Record<string, unknown>;
      approved: boolean;
      trace: AgentTraceEvent[];
    }>({
      path: "/api/stream/contract/generate",
      body: { text, domain, session_id: sessionId },
      onTrace,
    }),

  approveContract: (sessionId: string, contractYaml: string, onTrace: (event: AgentTraceEvent) => void) =>
    streamWorkflowRequest<{
      session_id: string;
      domain: string;
      contract_yaml: string;
      contract: Record<string, unknown>;
      approved: boolean;
      trace: AgentTraceEvent[];
    }>({
      path: "/api/stream/contract/approve",
      body: { session_id: sessionId, contract_yaml: contractYaml },
      onTrace,
    }),

  analyzeImpact: (sessionId: string, onTrace: (event: AgentTraceEvent) => void) =>
    streamWorkflowRequest<{
      session_id: string;
      processes: string[];
      modules: string[];
      files: import("./types").ImpactedFile[];
      trace: AgentTraceEvent[];
    }>({
      path: "/api/stream/impact/analyze",
      body: { session_id: sessionId },
      onTrace,
    }),

  scoreRisk: (sessionId: string, onTrace: (event: AgentTraceEvent) => void) =>
    streamWorkflowRequest<{
      session_id: string;
      assessment: import("./types").RiskAssessment;
      trace: AgentTraceEvent[];
    }>({
      path: "/api/stream/risk/score",
      body: { session_id: sessionId },
      onTrace,
    }),

  generateTests: (sessionId: string | undefined, onTrace: (event: AgentTraceEvent) => void) =>
    streamWorkflowRequest<{
      session_id: string;
      tests: import("./types").GeneratedTest[];
      trace: AgentTraceEvent[];
    }>({
      path: `/api/stream/tests/generate${sessionId ? `?session_id=${sessionId}` : ""}`,
      method: "POST",
      onTrace,
    }),

  runSimulation: (sessionId: string | undefined, onTrace: (event: AgentTraceEvent) => void) =>
    streamWorkflowRequest<{
      session_id: string;
      before: import("./types").SimulationCase[];
      after: import("./types").SimulationCase[];
      summary: string;
      trace: AgentTraceEvent[];
    }>({
      path: `/api/stream/simulation/run${sessionId ? `?session_id=${sessionId}` : ""}`,
      method: "POST",
      onTrace,
    }),

  evaluateGovernance: (sessionId: string, onTrace: (event: AgentTraceEvent) => void) =>
    streamWorkflowRequest<{
      session_id: string;
      evaluation: import("./types").GovernanceEvaluation;
      orchestration: import("./types").OrchestrationStatus;
      trace: AgentTraceEvent[];
    }>({
      path: `/api/stream/governance/evaluate?session_id=${sessionId}`,
      method: "GET",
      onTrace,
    }),

  generatePack: (sessionId: string, onTrace: (event: AgentTraceEvent) => void) =>
    streamWorkflowRequest<{
      session_id: string;
      pack_id: string;
      filename: string;
      markdown: string;
      trace: AgentTraceEvent[];
    }>({
      path: "/api/stream/pack/generate",
      body: { session_id: sessionId },
      onTrace,
    }),

  runAgent: (text: string, sessionId: string | undefined, onTrace: (event: AgentTraceEvent) => void) =>
    streamWorkflowRequest<import("./types").AgentWorkflowResult>({
      path: "/api/stream/workflow/run",
      body: { text, session_id: sessionId },
      onTrace,
    }),

  resumeAgent: (sessionId: string, onTrace: (event: AgentTraceEvent) => void) =>
    streamWorkflowRequest<import("./types").AgentWorkflowResult>({
      path: "/api/stream/workflow/resume",
      body: { session_id: sessionId },
      onTrace,
    }),
};

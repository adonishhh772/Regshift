import type { AgentTraceEvent, ChatMessage, ChatThinkingBlock, ThinkingStep, TraceStatus } from "./types";
import { parseApiErrorMessage } from "./apiErrors";

export type ThinkingWorkflowKey =
  | "classify"
  | "compile"
  | "approve"
  | "graph"
  | "risk"
  | "tests"
  | "simulation"
  | "governance"
  | "pack"
  | "agent"
  | "agent_resume";

export interface ThinkingPlan {
  headline: string;
}

export const THINKING_PLANS: Record<ThinkingWorkflowKey, ThinkingPlan> = {
  classify: { headline: "Analyzing business change request…" },
  compile: { headline: "Compiling change contract…" },
  approve: { headline: "Recording human approval…" },
  graph: { headline: "Tracing impact through the system…" },
  risk: { headline: "Scoring change risk…" },
  tests: { headline: "Generating contract-linked tests…" },
  simulation: { headline: "Running before/after simulation…" },
  governance: { headline: "Evaluating production gate…" },
  pack: { headline: "Generating approval-ready change pack…" },
  agent: { headline: "Running assurance agent…" },
  agent_resume: { headline: "Agent continuing workflow…" },
};

function createMessageId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createThinkingBlock(plan: ThinkingPlan): ChatThinkingBlock {
  return {
    headline: plan.headline,
    steps: [],
    isStreaming: true,
    subagentsExpanded: true,
    toolCallCount: 0,
  };
}

function mapTraceToThinkingStep(event: AgentTraceEvent, index: number): ThinkingStep {
  return {
    id: `trace-${index}-${event.timestamp}`,
    action: event.message,
    status: event.status,
    description: event.explanation ?? undefined,
    resultTag: event.evidence_count != null ? `${event.evidence_count} evidence` : undefined,
  };
}

export function createThinkingAssistantMessage(plan: ThinkingPlan): ChatMessage {
  return {
    id: createMessageId(),
    role: "assistant",
    content: "",
    timestamp: new Date().toISOString(),
    thinking: createThinkingBlock(plan),
  };
}

function buildThinkingPatch(plan: ThinkingPlan, steps: ThinkingStep[], isStreaming: boolean): Partial<ChatMessage> {
  return {
    thinking: {
      headline: isStreaming ? plan.headline : plan.headline.replace("…", ""),
      steps,
      isStreaming,
      subagentsExpanded: isStreaming,
      toolCallCount: steps.length,
    },
  };
}

export function finalizeThinkingMessage(
  messageId: string,
  plan: ThinkingPlan,
  steps: ThinkingStep[],
  summary: string,
  status: TraceStatus,
  updateMessage: (messageId: string, patch: Partial<ChatMessage>) => void
): void {
  updateMessage(messageId, {
    content: summary,
    status,
    ...buildThinkingPatch(plan, steps, false),
  });
}

export function failThinkingMessage(
  messageId: string,
  plan: ThinkingPlan,
  steps: ThinkingStep[],
  errorMessage: string,
  updateMessage: (messageId: string, patch: Partial<ChatMessage>) => void
): void {
  const friendlyMessage = parseApiErrorMessage(errorMessage);
  const errorSteps: ThinkingStep[] =
    steps.length > 0
      ? steps
      : [
          {
            id: "workflow-error",
            action: "Workflow step failed",
            description: friendlyMessage,
            status: "error",
          },
        ];

  updateMessage(messageId, {
    content: friendlyMessage,
    status: "error",
    thinking: {
      headline: plan.headline.replace("…", " — failed"),
      steps: errorSteps,
      isStreaming: false,
      subagentsExpanded: true,
      toolCallCount: errorSteps.length,
    },
  });
}

export async function runStreamingWorkflow<T extends { trace: AgentTraceEvent[] }>(
  plan: ThinkingPlan,
  streamAction: (onTrace: (event: AgentTraceEvent) => void) => Promise<T>,
  buildSummary: (result: T) => { content: string; status: TraceStatus },
  callbacks: {
    addMessage: (message: ChatMessage) => void;
    updateMessage: (messageId: string, patch: Partial<ChatMessage>) => void;
    setLoading: (loading: boolean) => void;
  }
): Promise<T> {
  const thinkingMessage = createThinkingAssistantMessage(plan);
  callbacks.addMessage(thinkingMessage);
  callbacks.setLoading(true);

  const streamedSteps: ThinkingStep[] = [];

  const handleTraceEvent = (event: AgentTraceEvent) => {
    streamedSteps.push(mapTraceToThinkingStep(event, streamedSteps.length));
    callbacks.updateMessage(
      thinkingMessage.id,
      buildThinkingPatch(plan, [...streamedSteps], true)
    );
  };

  try {
    const result = await streamAction(handleTraceEvent);
    const mergedSteps =
      result.trace.length > streamedSteps.length
        ? result.trace.map((event, index) => mapTraceToThinkingStep(event, index))
        : streamedSteps;
    const summary = buildSummary(result);
    finalizeThinkingMessage(
      thinkingMessage.id,
      plan,
      mergedSteps,
      summary.content,
      summary.status,
      callbacks.updateMessage
    );
    return result;
  } catch (error) {
    const rawMessage = error instanceof Error ? error.message : "Something went wrong";
    failThinkingMessage(
      thinkingMessage.id,
      plan,
      streamedSteps,
      parseApiErrorMessage(rawMessage),
      callbacks.updateMessage
    );
    throw error;
  } finally {
    callbacks.setLoading(false);
  }
}

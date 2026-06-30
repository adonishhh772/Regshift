import type { AgentWorkflowResult, ChatMessage } from "./types";

function createMessageId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function hasPendingContractApproval(messages: ChatMessage[]): boolean {
  return messages.some(
    (message) => message.contractApproval && !message.contractApproval.approved
  );
}

export function createContractApprovalMessage(result: AgentWorkflowResult): ChatMessage | null {
  if (result.status !== "paused" || result.pause_gate !== "human_approval" || !result.contract_yaml) {
    return null;
  }

  return {
    id: createMessageId(),
    role: "assistant",
    content:
      "I've compiled the change contract from your policy graph. Review the YAML below, edit if needed, then approve to let the agent continue.",
    timestamp: new Date().toISOString(),
    status: "blocked",
    contractApproval: {
      contractYaml: result.contract_yaml,
      domain: result.domain ?? null,
      approved: false,
    },
  };
}

export function markContractApprovalMessagesApproved(messages: ChatMessage[]): ChatMessage[] {
  return messages.map((message) => {
    if (!message.contractApproval || message.contractApproval.approved) {
      return message;
    }
    return {
      ...message,
      status: "completed",
      contractApproval: {
        ...message.contractApproval,
        approved: true,
      },
    };
  });
}

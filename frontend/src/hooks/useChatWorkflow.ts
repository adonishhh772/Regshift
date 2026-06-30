"use client";

import { useCallback, useMemo } from "react";

import { CHAT_COMMAND_APPROVE, CHAT_COMMAND_HELP, resolveChatCommand } from "@/lib/chatCommands";
import {
  createContractApprovalMessage,
  hasPendingContractApproval,
  markContractApprovalMessagesApproved,
} from "@/lib/chatContractApproval";
import { useWorkflowActions } from "@/hooks/useWorkflowActions";
import { parseApiErrorMessage } from "@/lib/apiErrors";
import { normalizeFetchError } from "@/lib/networkErrors";
import { useRegShiftStore } from "@/lib/store";
import type { AgentWorkflowResult, ChatMessage, TraceStatus } from "@/lib/types";
import { THINKING_PLANS, runStreamingWorkflow } from "@/lib/workflowThinking";

function createMessage(role: ChatMessage["role"], content: string, status?: ChatMessage["status"]): ChatMessage {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    role,
    content,
    timestamp: new Date().toISOString(),
    status,
  };
}

function buildHelpMessage(): string {
  return [
    "The assurance agent runs the full workflow for you:",
    "",
    "1. Describe your business change (10+ characters) — agent classifies and compiles the contract",
    "2. Review and approve the contract in the chat message when the human gate appears",
    "3. The agent runs impact, graph, tests, simulation, governance, and pack",
    "",
    "All steps stream live with Langfuse tracing.",
  ].join("\n");
}

function agentResultStatus(result: AgentWorkflowResult): TraceStatus {
  if (result.status === "completed") {
    return "completed";
  }
  if (result.status === "blocked") {
    return "blocked";
  }
  return "completed";
}

export function useChatWorkflow() {
  const store = useRegShiftStore();
  const actions = useWorkflowActions();

  const thinkingCallbacks = useMemo(
    () => ({
      addMessage: store.addChatMessage,
      updateMessage: store.updateChatMessage,
      setLoading: store.setLoading,
    }),
    [store.addChatMessage, store.setLoading, store.updateChatMessage]
  );

  const pushAssistantMessage = useCallback(
    (content: string, status?: ChatMessage["status"]) => {
      store.addChatMessage(createMessage("assistant", content, status));
    },
    [store]
  );

  const pushUserMessage = useCallback(
    (content: string) => {
      store.addChatMessage(createMessage("user", content));
    },
    [store]
  );

  const addContractApprovalMessageIfNeeded = useCallback(
    (result: AgentWorkflowResult) => {
      if (hasPendingContractApproval(useRegShiftStore.getState().chatMessages)) {
        return;
      }
      const approvalMessage = createContractApprovalMessage(result);
      if (approvalMessage) {
        store.addChatMessage(approvalMessage);
      }
    },
    [store]
  );

  const handleContractYamlChange = useCallback(
    (messageId: string, contractYaml: string) => {
      const message = useRegShiftStore.getState().chatMessages.find((item) => item.id === messageId);
      if (!message?.contractApproval || message.contractApproval.approved) {
        return;
      }
      store.updateChatMessage(messageId, {
        contractApproval: {
          ...message.contractApproval,
          contractYaml,
        },
      });
      store.setContractYaml(contractYaml);
    },
    [store]
  );

  const handleApproveWorkflow = useCallback(async () => {
    if (!store.sessionId) {
      pushAssistantMessage("No active session. Describe your business change first.", "blocked");
      return;
    }
    if (!store.contractYaml) {
      pushAssistantMessage("No contract to approve yet. Describe your change so the agent can compile a contract.", "blocked");
      return;
    }
    store.setError(null);
    try {
      await runStreamingWorkflow(
        THINKING_PLANS.agent_resume,
        actions.executeAgentResumeStream,
        (result) => ({
          content: result.summary,
          status: agentResultStatus(result),
        }),
        thinkingCallbacks
      );
      store.setChatMessages(
        markContractApprovalMessagesApproved(useRegShiftStore.getState().chatMessages)
      );
    } catch (error) {
      const errorMessage = parseApiErrorMessage(normalizeFetchError(error));
      store.setError(errorMessage);
    }
  }, [actions, pushAssistantMessage, store, thinkingCallbacks]);

  const handleApproveForMessage = useCallback(
    async (messageId: string) => {
      const message = useRegShiftStore.getState().chatMessages.find((item) => item.id === messageId);
      if (message?.contractApproval?.contractYaml) {
        store.setContractYaml(message.contractApproval.contractYaml);
      }
      await handleApproveWorkflow();
    },
    [handleApproveWorkflow, store]
  );

  const handleSendMessage = useCallback(
    async (rawMessage: string) => {
      const message = rawMessage.trim();
      if (!message) {
        return;
      }

      pushUserMessage(message);
      store.setError(null);

      if (store.backendStatus === "offline") {
        pushAssistantMessage("Backend is unreachable. Check that the API is running on port 8000.", "error");
        return;
      }

      const command = resolveChatCommand(message);

      try {
        if (command === CHAT_COMMAND_HELP) {
          pushAssistantMessage(buildHelpMessage());
          return;
        }

        if (command === CHAT_COMMAND_APPROVE) {
          if (!store.sessionId) {
            pushAssistantMessage("No active session. Describe your business change first.", "blocked");
            return;
          }
          await handleApproveWorkflow();
          return;
        }

        if (message.length >= 10) {
          store.setChangeText(message);
          const result = await runStreamingWorkflow(
            THINKING_PLANS.agent,
            actions.executeAgentStartStream,
            (agentResult) => ({
              content: agentResult.summary,
              status: agentResultStatus(agentResult),
            }),
            thinkingCallbacks
          );
          addContractApprovalMessageIfNeeded(result);
          return;
        }

        pushAssistantMessage(
          "Describe your business change in at least 10 characters. The agent will classify it and compile the contract automatically."
        );
      } catch (error) {
        const errorMessage = parseApiErrorMessage(normalizeFetchError(error));
        store.setError(errorMessage);
      }
    },
    [
      actions,
      addContractApprovalMessageIfNeeded,
      handleApproveWorkflow,
      pushAssistantMessage,
      pushUserMessage,
      store,
      thinkingCallbacks,
    ]
  );

  const awaitingContractApproval = hasPendingContractApproval(store.chatMessages);

  return {
    messages: store.chatMessages,
    isLoading: store.isLoading,
    backendStatus: store.backendStatus,
    sessionId: store.sessionId,
    domain: store.domain,
    awaitingContractApproval,
    handleSendMessage,
    handleApproveForMessage,
    handleContractYamlChange,
  };
}

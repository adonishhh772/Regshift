import { CHAT_COMMAND_APPROVE } from "./chatCommands";

interface PrerequisiteState {
  sessionId: string | null;
  contractYaml: string;
}

export function getChatCommandPrerequisiteError(command: string, state: PrerequisiteState): string | null {
  if (command === CHAT_COMMAND_APPROVE) {
    if (!state.sessionId) {
      return "No active session. Describe your business change first.";
    }
    if (!state.contractYaml.trim()) {
      return "No contract to approve yet. Describe your change so the agent can compile a contract.";
    }
    return null;
  }

  return null;
}

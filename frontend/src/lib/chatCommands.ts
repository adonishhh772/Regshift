export const CHAT_COMMAND_APPROVE = "approve contract";
export const CHAT_COMMAND_HELP = "help";

export const CHAT_QUICK_ACTIONS = [
  { id: CHAT_COMMAND_APPROVE, label: "Approve & continue agent" },
  { id: CHAT_COMMAND_HELP, label: "Help" },
] as const;

export function resolveChatCommand(message: string): string | null {
  const normalized = message.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized === CHAT_COMMAND_HELP || normalized === "?") {
    return CHAT_COMMAND_HELP;
  }
  const commands = [
    CHAT_COMMAND_APPROVE,
    CHAT_COMMAND_HELP,
  ];
  for (const command of commands) {
    if (normalized === command || normalized.includes(command)) {
      return command;
    }
  }
  return null;
}

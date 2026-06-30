"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";

import { ChatContractApproval } from "@/components/ChatContractApproval";
import { WorkflowThinkingCard } from "@/components/WorkflowThinkingCard";
import { CHAT_COMMAND_APPROVE, CHAT_QUICK_ACTIONS } from "@/lib/chatCommands";
import { useChatWorkflow } from "@/hooks/useChatWorkflow";

export function ChatPanel() {
  const {
    messages,
    isLoading,
    backendStatus,
    sessionId,
    domain,
    awaitingContractApproval,
    handleSendMessage,
    handleApproveForMessage,
    handleContractYamlChange,
  } = useChatWorkflow();
  const [inputValue, setInputValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, awaitingContractApproval]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = inputValue.trim();
    if (!message || isLoading) {
      return;
    }
    setInputValue("");
    await handleSendMessage(message);
  };

  const handleQuickAction = async (command: string) => {
    if (isLoading) {
      return;
    }
    await handleSendMessage(command);
  };

  const handleApproveClick = async (messageId: string) => {
    if (isLoading) {
      return;
    }
    await handleApproveForMessage(messageId);
  };

  const handleContractChange = (messageId: string, contractYaml: string) => {
    handleContractYamlChange(messageId, contractYaml);
  };

  return (
    <div data-testid="chat-panel" className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-4xl flex-col gap-4">
      <section className="glass-card shrink-0 rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">RegShift Assistant</p>
        <h2 className="mt-2 text-2xl font-semibold">Describe your change — the agent runs the full workflow</h2>
        <p className="mt-2 text-sm text-slate-600">
          {backendStatus === "offline"
            ? "Backend is unreachable. Start the API on port 8000, then refresh."
            : "When the contract is ready, review and approve it in the chat thread to continue the agent."}
        </p>
        {sessionId ? (
          <p className="mt-3 text-xs text-slate-500">
            Active session: {sessionId.slice(0, 8)}… {domain ? `· ${domain}` : ""}
          </p>
        ) : null}
      </section>

      <section className="glass-card flex min-h-0 flex-1 flex-col rounded-2xl border border-[#e8e4df] bg-[#FAF9F7] shadow-sm">
        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {messages.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#e8e4df] bg-white p-6 text-sm text-slate-600">
              Example: &quot;Increase procurement approval threshold from £10,000 to £25,000 for ERPNext purchase
              orders.&quot;
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                data-testid={`chat-message-${message.role}`}
                className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {message.role === "user" ? (
                  <div className="max-w-[85%] rounded-2xl bg-gradient-to-r from-orange-500 to-red-500 px-4 py-3 text-sm text-white whitespace-pre-wrap">
                    {message.content}
                  </div>
                ) : message.contractApproval ? (
                  <ChatContractApproval
                    messageId={message.id}
                    content={message.content}
                    approval={message.contractApproval}
                    isLoading={isLoading}
                    onContractYamlChange={handleContractChange}
                    onApprove={handleApproveClick}
                  />
                ) : message.thinking ? (
                  <WorkflowThinkingCard message={message} />
                ) : (
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
                      message.status === "error"
                        ? "border border-red-200 bg-red-50 text-red-800"
                        : "border border-[#e8e4df] bg-white text-slate-700"
                    }`}
                  >
                    {message.content}
                  </div>
                )}
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="border-t border-[#e8e4df] bg-white p-4">
          <div className="mb-3 flex flex-wrap gap-2">
            {CHAT_QUICK_ACTIONS.map((action) => (
              <button
                key={action.id}
                type="button"
                data-testid={`chat-quick-${action.id.replace(/\s+/g, "-")}`}
                disabled={
                  isLoading ||
                  backendStatus === "offline" ||
                  (!awaitingContractApproval && action.id === CHAT_COMMAND_APPROVE)
                }
                onClick={() => handleQuickAction(action.id)}
                className="rounded-full border border-[#e8e4df] bg-[#FAF9F7] px-3 py-1 text-xs text-slate-600 transition hover:border-orange-200 disabled:opacity-50"
              >
                {action.label}
              </button>
            ))}
          </div>
          <form onSubmit={handleSubmit} className="flex gap-3">
            <input
              data-testid="chat-input"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder={
                awaitingContractApproval
                  ? "Review the contract in chat, then click Approve…"
                  : "Describe a business change or type a command…"
              }
              disabled={isLoading || backendStatus === "offline"}
              className="glass-input flex-1 rounded-xl border border-[#e8e4df] bg-[#FAF9F7] px-4 py-3 text-sm outline-none ring-orange-500/10 focus:ring-2 disabled:opacity-50"
            />
            <button
              type="submit"
              data-testid="chat-send-button"
              disabled={isLoading || backendStatus === "offline" || inputValue.trim().length === 0}
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-orange-500 to-red-500 px-4 py-3 text-sm font-medium text-white disabled:opacity-50"
            >
              <Send size={16} />
              Send
            </button>
          </form>
        </div>
      </section>
    </div>
  );
}

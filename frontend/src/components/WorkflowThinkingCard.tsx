"use client";

import { AlertCircle, ChevronDown, ChevronRight, Loader2 } from "lucide-react";

import { useRegShiftStore } from "@/lib/store";
import type { ChatMessage, ThinkingStep } from "@/lib/types";

interface WorkflowThinkingCardProps {
  message: ChatMessage;
}

const STATUS_DOT: Record<string, string> = {
  completed: "bg-emerald-500",
  active: "bg-blue-500 animate-pulse",
  blocked: "bg-amber-500",
  pending: "bg-slate-300",
  error: "bg-red-500",
};

function ThinkingStepRow({ step, isLast }: { step: ThinkingStep; isLast: boolean }) {
  return (
    <div className="relative flex gap-3 pb-4" data-testid={`thinking-step-${step.id}`}>
      {!isLast ? <span className="absolute left-[7px] top-5 h-full w-px bg-slate-200" aria-hidden /> : null}
      <span className={`mt-1 h-3.5 w-3.5 shrink-0 rounded-full ${STATUS_DOT[step.status] ?? STATUS_DOT.pending}`} />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-slate-900">{step.action}</p>
        {step.description ? <p className="mt-0.5 text-xs text-slate-500">{step.description}</p> : null}
        {step.resultTag ? (
          <span className="mt-2 inline-block rounded-md bg-slate-900 px-2 py-1 font-mono text-[10px] text-white">
            {step.resultTag}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export function WorkflowThinkingCard({ message }: WorkflowThinkingCardProps) {
  const toggleChatThinkingExpanded = useRegShiftStore((state) => state.toggleChatThinkingExpanded);
  const thinking = message.thinking;
  const isError = message.status === "error";

  if (!thinking) {
    return null;
  }

  const handleToggleSubagents = () => {
    toggleChatThinkingExpanded(message.id);
  };

  return (
    <div
      data-testid="workflow-thinking-card"
      className={`w-full max-w-2xl overflow-hidden rounded-2xl border bg-white shadow-sm ${
        isError ? "border-red-200" : "border-[#e8e4df]"
      }`}
    >
      <div className={`border-b px-4 py-3 ${isError ? "border-red-200 bg-red-50" : "border-[#e8e4df]"}`}>
        <div className="flex items-center gap-2">
          {thinking.isStreaming ? (
            <Loader2 size={16} className="animate-spin text-blue-600" />
          ) : isError ? (
            <AlertCircle size={16} className="text-red-600" />
          ) : null}
          <p className={`text-sm font-medium ${isError ? "text-red-900" : "text-slate-900"}`}>{thinking.headline}</p>
        </div>
      </div>

      <div className="px-4 py-3">
        <button
          type="button"
          data-testid="toggle-subagents-button"
          onClick={handleToggleSubagents}
          className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500"
        >
          {thinking.subagentsExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          Running subagents
        </button>

        {thinking.subagentsExpanded ? (
          <div className="mt-3 max-h-64 overflow-y-auto pl-1" data-testid="thinking-subagents-list">
            {thinking.steps.length === 0 ? (
              <p className="text-xs text-slate-500">Waiting for backend agents…</p>
            ) : (
              thinking.steps.map((step, index) => (
                <ThinkingStepRow key={step.id} step={step} isLast={index === thinking.steps.length - 1} />
              ))
            )}
          </div>
        ) : null}
      </div>

      {!thinking.isStreaming ? (
        <div
          className={`flex items-center justify-between border-t px-4 py-3 text-xs ${
            isError ? "border-red-200 bg-red-50 text-red-700" : "border-[#e8e4df] bg-[#FAF9F7] text-slate-600"
          }`}
        >
          <span data-testid="tool-calls-completed">
            {isError
              ? "Step could not complete"
              : `${thinking.toolCallCount} tool call${thinking.toolCallCount === 1 ? "" : "s"} completed`}
          </span>
          {!isError ? (
            <button type="button" onClick={handleToggleSubagents} className="font-medium text-blue-600">
              View all
            </button>
          ) : null}
        </div>
      ) : null}

      {message.content && !isError ? (
        <div className="border-t border-[#e8e4df] px-4 py-3 text-sm leading-6 text-slate-700 whitespace-pre-wrap">
          {message.content}
        </div>
      ) : null}

      {message.content && isError ? (
        <div
          data-testid="workflow-thinking-error"
          className="border-t border-red-200 bg-red-50 px-4 py-3"
        >
          <p className="text-sm font-medium text-red-900">What went wrong</p>
          <p className="mt-1 text-sm leading-6 text-red-800">{message.content}</p>
        </div>
      ) : null}
    </div>
  );
}

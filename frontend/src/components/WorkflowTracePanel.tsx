"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity } from "lucide-react";

import { api } from "@/lib/api";
import { useRegShiftStore } from "@/lib/store";
import type { WorkflowTraceSummary } from "@/lib/types";

const STEP_STATUS_STYLES: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-700",
  active: "bg-blue-100 text-blue-700",
  blocked: "bg-red-100 text-red-700",
  pending: "bg-slate-100 text-slate-500",
};

export function WorkflowTracePanel() {
  const sessionId = useRegShiftStore((state) => state.sessionId);
  const langfuseUiUrl = useRegShiftStore((state) => state.langfuseUiUrl);
  const setLangfuseUiUrl = useRegShiftStore((state) => state.setLangfuseUiUrl);
  const [traceSummary, setTraceSummary] = useState<WorkflowTraceSummary | null>(null);

  const loadTraceSummary = useCallback(async () => {
    if (!sessionId) {
      setTraceSummary(null);
      return;
    }
    try {
      const summary = await api.getWorkflowTrace(sessionId);
      setTraceSummary(summary);
      if (summary.langfuse.session_trace_url) {
        setLangfuseUiUrl(summary.langfuse.session_trace_url);
      }
    } catch {
      setTraceSummary(null);
    }
  }, [sessionId, setLangfuseUiUrl]);

  useEffect(() => {
    loadTraceSummary().catch(() => undefined);
  }, [loadTraceSummary]);

  if (!sessionId) {
    return null;
  }

  return (
    <section data-testid="workflow-trace-panel" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-blue-100 p-2 text-blue-600">
            <Activity size={20} />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Workflow Trace</p>
            <p className="mt-1 text-sm text-slate-600">Full LangGraph pipeline traced in Langfuse per session</p>
          </div>
        </div>
        <button
          type="button"
          data-testid="refresh-workflow-trace-button"
          onClick={loadTraceSummary}
          className="glass-button rounded-xl border border-[#e8e4df] px-4 py-2 text-sm font-medium text-slate-700"
        >
          Refresh Trace
        </button>
      </div>

      {traceSummary ? (
        <>
          <div className="mb-4 flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-[#FAF9F7] px-3 py-1">Current: {traceSummary.current_step}</span>
            <span className="rounded-full bg-[#FAF9F7] px-3 py-1">Gate: {traceSummary.gate_status}</span>
            {langfuseUiUrl ? (
              <a
                href={langfuseUiUrl}
                target="_blank"
                rel="noreferrer"
                data-testid="session-langfuse-link"
                className="rounded-full bg-purple-100 px-3 py-1 font-medium text-purple-700 hover:bg-purple-200"
              >
                View session in Langfuse
              </a>
            ) : null}
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {traceSummary.steps.map((step) => (
              <div
                key={step.id}
                data-testid={`workflow-trace-step-${step.id}`}
                className="flex items-center justify-between rounded-xl border border-[#e8e4df] bg-[#FAF9F7] px-3 py-2"
              >
                <span className="text-xs font-medium text-slate-700">{step.id.replace(/_/g, " ")}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                    STEP_STATUS_STYLES[step.status] ?? STEP_STATUS_STYLES.pending
                  }`}
                >
                  {step.status}
                </span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="text-sm text-slate-500">Run classify to start a traced workflow session.</p>
      )}
    </section>
  );
}

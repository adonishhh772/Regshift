"use client";

import { useRegShiftStore } from "@/lib/store";

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-emerald-500",
  active: "bg-blue-500",
  blocked: "bg-amber-500",
  pending: "bg-slate-300",
  error: "bg-red-500",
};

export function AgentTrace() {
  const trace = useRegShiftStore((state) => state.trace);

  return (
    <aside
      data-testid="agent-trace"
      className="flex w-[320px] shrink-0 flex-col border-l border-[#e8e4df] bg-white/80 backdrop-blur-xl"
    >
      <div className="border-b border-[#e8e4df] px-4 py-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tool Calls</p>
        <h3 className="text-sm font-semibold">Agent Trace</h3>
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        <div className="space-y-3">
          {trace.length === 0 ? (
            <p className="text-xs text-slate-500">Agent activity will appear here as you progress through the workflow.</p>
          ) : (
            trace.map((event, index) => (
              <div key={`${event.timestamp}-${index}`} className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-3">
                <div className="flex items-start gap-2">
                  <span className={`mt-1 h-2 w-2 rounded-full ${STATUS_COLORS[event.status] ?? STATUS_COLORS.pending}`} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium">{event.message}</p>
                    <p className="mt-1 text-[10px] text-slate-500">{new Date(event.timestamp).toLocaleTimeString()}</p>
                    {event.explanation ? <p className="mt-2 text-xs text-slate-600">{event.explanation}</p> : null}
                    {event.evidence_count != null ? (
                      <p className="mt-1 text-[10px] uppercase tracking-wider text-orange-700">
                        Evidence: {event.evidence_count}
                      </p>
                    ) : null}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </aside>
  );
}

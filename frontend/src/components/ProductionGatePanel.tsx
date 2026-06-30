"use client";

import type { GovernanceEvaluation } from "@/lib/types";
import { useRegShiftStore } from "@/lib/store";

interface ProductionGatePanelProps {
  onEvaluateGovernance: () => void;
}

const GATE_STYLES: Record<string, string> = {
  open: "border-emerald-200 bg-emerald-50 text-emerald-800",
  conditional: "border-amber-200 bg-amber-50 text-amber-800",
  blocked: "border-red-200 bg-red-50 text-red-800",
};

export function ProductionGatePanel({ onEvaluateGovernance }: ProductionGatePanelProps) {
  const governance = useRegShiftStore((state) => state.governance);
  const orchestration = useRegShiftStore((state) => state.orchestration);
  const graphBackend = useRegShiftStore((state) => state.graphBackend);
  const isLoading = useRegShiftStore((state) => state.isLoading);

  const gateStatus = governance?.gate_status ?? orchestration?.gate_status ?? "blocked";

  return (
    <section data-testid="production-gate-panel" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Production Gate</p>
          <p className="mt-1 text-sm text-slate-600">Policy knowledge graph · LangGraph workflow · Langfuse tracing</p>
        </div>
        <button
          type="button"
          data-testid="evaluate-governance-button"
          disabled={isLoading}
          onClick={onEvaluateGovernance}
          className="rounded-xl bg-gradient-to-r from-orange-500 to-red-500 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:opacity-50"
        >
          Evaluate Production Gate
        </button>
      </div>

      <div className="mb-4 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-[#FAF9F7] px-3 py-1">Orchestrator: LangGraph</span>
        <span data-testid="graph-backend-badge" className="rounded-full bg-[#FAF9F7] px-3 py-1">
          Graph: {graphBackend}
        </span>
        {orchestration ? (
          <span className="rounded-full bg-[#FAF9F7] px-3 py-1">Step: {orchestration.current_step}</span>
        ) : null}
      </div>

      <div data-testid="gate-status-banner" className={`rounded-xl border px-4 py-3 text-sm font-medium ${GATE_STYLES[gateStatus] ?? GATE_STYLES.blocked}`}>
        {governance?.summary ?? "Run simulation, then evaluate production gate before generating change pack."}
      </div>

      {governance ? (
        <div className="mt-4 space-y-2">
          {governance.checks.map((check) => (
            <GovernanceCheckRow key={check.id} check={check} />
          ))}
        </div>
      ) : null}
    </section>
  );
}

function GovernanceCheckRow({ check }: { check: GovernanceEvaluation["checks"][number] }) {
  return (
    <div
      data-testid={`governance-check-${check.id}`}
      className="flex items-start justify-between gap-3 rounded-xl border border-[#e8e4df] bg-[#FAF9F7] px-4 py-3"
    >
      <div>
        <p className="text-sm font-medium">{check.name}</p>
        <p className="mt-1 text-xs text-slate-600">{check.explanation}</p>
      </div>
      <span
        className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
          check.passed ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
        }`}
      >
        {check.passed ? "pass" : check.severity}
      </span>
    </div>
  );
}

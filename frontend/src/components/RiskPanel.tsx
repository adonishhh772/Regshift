"use client";

import { useRegShiftStore } from "@/lib/store";

interface RiskPanelProps {
  onScoreRisk: () => void;
}

export function RiskPanel({ onScoreRisk }: RiskPanelProps) {
  const risks = useRegShiftStore((state) => state.risks);
  const isLoading = useRegShiftStore((state) => state.isLoading);

  return (
    <section data-testid="risk-panel" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Risk</p>
        <button
          type="button"
          data-testid="score-risk-button"
          disabled={isLoading}
          onClick={onScoreRisk}
          className="rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium shadow-sm disabled:opacity-50"
        >
          Score Risk
        </button>
      </div>
      {risks ? (
        <>
          <div className="grid gap-2 md:grid-cols-2">
            {Object.entries(risks.risks).map(([name, level]) => (
              <div key={name} className="flex items-center justify-between rounded-xl border border-[#e8e4df] bg-[#FAF9F7] px-4 py-3">
                <span className="text-sm capitalize">{name.replace(/_/g, " ")}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wider ${
                    level === "high" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
                  }`}
                >
                  {level}
                </span>
              </div>
            ))}
          </div>
          <div data-testid="agent-blocked-message" className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            {risks.blocked_message}
          </div>
          <div className="mt-4 grid gap-2 text-xs text-slate-600 md:grid-cols-2">
            {Object.entries(risks.agent_limits).map(([key, value]) => (
              <div key={key} className="rounded-lg bg-[#FAF9F7] px-3 py-2">
                {key}: <strong>{String(value)}</strong>
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="text-sm text-slate-500">Run impact analysis, then score risks.</p>
      )}
    </section>
  );
}

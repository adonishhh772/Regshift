"use client";

import { useRegShiftStore } from "@/lib/store";

interface SimulationPanelProps {
  onRunSimulation: () => void;
}

export function SimulationPanel({ onRunSimulation }: SimulationPanelProps) {
  const simulationBefore = useRegShiftStore((state) => state.simulationBefore);
  const simulationAfter = useRegShiftStore((state) => state.simulationAfter);
  const simulationSummary = useRegShiftStore((state) => state.simulationSummary);
  const isLoading = useRegShiftStore((state) => state.isLoading);

  return (
    <section data-testid="simulation-panel" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Simulation</p>
        <button
          type="button"
          data-testid="run-simulation-button"
          disabled={isLoading}
          onClick={onRunSimulation}
          className="rounded-xl bg-gradient-to-r from-orange-500 to-red-500 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:opacity-50"
        >
          Run Simulation
        </button>
      </div>
      {simulationSummary ? <p className="mb-4 text-sm text-slate-600">{simulationSummary}</p> : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <SimulationTable title="Before Proposed Change" cases={simulationBefore} />
        <SimulationTable title="After Proposed Change" cases={simulationAfter} />
      </div>
    </section>
  );
}

function SimulationTable({
  title,
  cases,
}: {
  title: string;
  cases: { label: string; amount: number; approval: string; result: string; verdict: string }[];
}) {
  return (
    <div className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4">
      <h3 className="text-sm font-medium">{title}</h3>
      <table className="mt-3 w-full text-left text-xs">
        <thead>
          <tr className="text-slate-500">
            <th className="pb-2">Case</th>
            <th className="pb-2">Amount</th>
            <th className="pb-2">Result</th>
            <th className="pb-2">Verdict</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((simCase) => (
            <tr key={`${title}-${simCase.label}`} className="border-t border-[#e8e4df]">
              <td className="py-2">{simCase.label}</td>
              <td className="py-2">£{simCase.amount.toLocaleString()}</td>
              <td className="py-2">{simCase.result}</td>
              <td className="py-2">
                <span
                  className={`rounded-full px-2 py-0.5 font-medium ${
                    simCase.verdict === "pass" ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"
                  }`}
                >
                  {simCase.verdict}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

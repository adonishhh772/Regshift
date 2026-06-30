"use client";

import { useRegShiftStore } from "@/lib/store";
import type { IdentifiedSystem } from "@/lib/types";

interface SystemsPanelProps {
  onConfirmSystems: () => void;
}

export function SystemsPanel({ onConfirmSystems }: SystemsPanelProps) {
  const systems = useRegShiftStore((state) => state.targetSystems);
  const systemsConfirmed = useRegShiftStore((state) => state.systemsConfirmed);
  const isLoading = useRegShiftStore((state) => state.isLoading);

  if (!systems || systems.systems.length === 0) {
    return null;
  }

  const handleConfirm = () => {
    onConfirmSystems();
  };

  return (
    <section
      data-testid="systems-panel"
      className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Target Systems</p>
          <p className="mt-1 text-sm text-slate-600">
            Identified from your change text and the registered system catalog.
          </p>
        </div>
        {systems.needs_confirmation && !systemsConfirmed ? (
          <button
            type="button"
            data-testid="confirm-systems-button"
            disabled={isLoading}
            onClick={handleConfirm}
            className="rounded-xl bg-gradient-to-r from-teal-500 to-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:opacity-50"
          >
            Confirm Systems
          </button>
        ) : null}
      </div>

      <ul className="space-y-2">
        {systems.systems.map((system: IdentifiedSystem) => (
          <li
            key={system.system_id}
            data-testid={`system-row-${system.system_id}`}
            className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] px-4 py-3 text-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-medium">{system.name}</p>
                <p className="text-xs text-slate-500">
                  {system.vendor} · {system.role} · {Math.round(system.confidence * 100)}% confidence
                </p>
              </div>
              <span
                className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wider ${
                  system.ingested
                    ? "border border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border border-amber-200 bg-amber-50 text-amber-700"
                }`}
              >
                {system.ingested ? "KG ready" : "Not ingested"}
              </span>
            </div>
          </li>
        ))}
      </ul>

      {systemsConfirmed ? (
        <p data-testid="systems-confirmed-banner" className="mt-3 text-xs text-emerald-700">
          Systems confirmed. Impact analysis will use the stored knowledge graph for these systems.
        </p>
      ) : null}
    </section>
  );
}

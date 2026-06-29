"use client";

import { DEMO_SCENARIOS } from "@/lib/demoScenarios";

interface ScenarioCardsProps {
  onSelect: (text: string, domain: string) => void;
}

export function ScenarioCards({ onSelect }: ScenarioCardsProps) {
  return (
    <section data-testid="scenario-cards" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
      <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Example Scenarios</p>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {DEMO_SCENARIOS.map((scenario) => (
          <button
            key={scenario.id}
            type="button"
            data-testid={`scenario-${scenario.id}`}
            onClick={() => onSelect(scenario.text, scenario.domain)}
            className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4 text-left transition hover:border-orange-200 hover:shadow-sm"
          >
            <p className="text-sm font-semibold">{scenario.title}</p>
            <p className="mt-2 line-clamp-3 text-xs leading-5 text-slate-600">{scenario.text}</p>
          </button>
        ))}
      </div>
    </section>
  );
}

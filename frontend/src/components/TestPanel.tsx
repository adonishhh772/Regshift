"use client";

import { useRegShiftStore } from "@/lib/store";

interface TestPanelProps {
  onGenerateTests: () => void;
}

export function TestPanel({ onGenerateTests }: TestPanelProps) {
  const tests = useRegShiftStore((state) => state.tests);
  const isLoading = useRegShiftStore((state) => state.isLoading);

  return (
    <section data-testid="test-panel" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Assurance</p>
        <button
          type="button"
          data-testid="generate-tests-button"
          disabled={isLoading}
          onClick={onGenerateTests}
          className="rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium shadow-sm disabled:opacity-50"
        >
          Generate Tests
        </button>
      </div>
      <div className="space-y-4">
        {tests.map((test) => (
          <div key={test.id} className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4">
            <p className="text-sm font-medium">{test.name}</p>
            <p className="mt-1 text-xs text-slate-500">Rule: {test.contract_rule}</p>
            <pre className="mt-3 overflow-x-auto rounded-lg bg-[#1a1a1a] p-3 text-xs text-emerald-300">{test.pytest_code}</pre>
          </div>
        ))}
      </div>
    </section>
  );
}

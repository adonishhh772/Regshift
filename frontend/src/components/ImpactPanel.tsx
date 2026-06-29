"use client";

import { useRegShiftStore } from "@/lib/store";

export function ImpactPanel() {
  const processes = useRegShiftStore((state) => state.processes);
  const modules = useRegShiftStore((state) => state.modules);
  const files = useRegShiftStore((state) => state.files);

  return (
    <section data-testid="impact-panel" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
      <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Impact</p>
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <h3 className="text-sm font-medium">Business Processes</h3>
          <ul className="mt-2 space-y-1 text-sm text-slate-600">
            {processes.map((process) => (
              <li key={process}>• {process}</li>
            ))}
          </ul>
          <h3 className="mt-4 text-sm font-medium">ERP Modules</h3>
          <ul className="mt-2 space-y-1 text-sm text-slate-600">
            {modules.map((module) => (
              <li key={module}>• {module}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-medium">Impacted Files</h3>
          <div className="mt-2 space-y-3">
            {files.map((file) => (
              <div key={file.path} className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-3">
                <div className="flex items-center justify-between gap-2">
                  <code className="text-xs">{file.path}</code>
                  <span className="rounded-full bg-orange-50 px-2 py-0.5 text-xs text-orange-700">{file.score}</span>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-600">{file.evidence_snippet}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

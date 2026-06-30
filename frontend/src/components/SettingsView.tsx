"use client";

import { useRegShiftStore } from "@/lib/store";

export function SettingsView() {
  const backendStatus = useRegShiftStore((state) => state.backendStatus);
  const graphBackend = useRegShiftStore((state) => state.graphBackend);
  const langfuseUiUrl = useRegShiftStore((state) => state.langfuseUiUrl);
  const indexStatus = useRegShiftStore((state) => state.indexStatus);

  return (
    <div data-testid="settings-view" className="mx-auto flex max-w-3xl flex-col gap-6">
      <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Settings</p>
        <h2 className="mt-2 text-2xl font-semibold">System configuration</h2>
        <p className="mt-2 text-sm text-slate-600">Connection details for the local RegShift stack.</p>
      </section>

      <section className="glass-card space-y-4 rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
        <SettingRow label="API URL" value={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"} />
        <SettingRow label="Backend status" value={backendStatus} />
        <SettingRow label="Graph backend" value={graphBackend} />
        <SettingRow
          label="Code index source"
          value={
            indexStatus
              ? indexStatus.source === "demo_seed"
                ? `${indexStatus.file_count} files · demo seed (clone ERPNext for real index)`
                : `${indexStatus.file_count} files · ${indexStatus.source}`
              : "Not loaded"
          }
        />
        <SettingRow
          label="Demo policy seed"
          value="Set SEED_DEMO_POLICIES=false in .env to disable auto demo policy on startup"
        />
        <SettingRow
          label="Langfuse UI"
          value={langfuseUiUrl ?? "Not configured — set LANGFUSE_PUBLIC_KEY to match LANGFUSE_INIT_PROJECT_PUBLIC_KEY in .env"}
        />
        <SettingRow label="Frontend" value="http://localhost:3000" />
      </section>
    </div>
  );
}

function SettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 border-b border-[#e8e4df] pb-4 last:border-b-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <span className="text-sm text-slate-500">{value}</span>
    </div>
  );
}

"use client";

import { RefreshCw } from "lucide-react";

import { BackendStatusBadge } from "@/components/BackendStatusBadge";
import { api } from "@/lib/api";
import { useRegShiftStore } from "@/lib/store";

export function TopBar() {
  const indexStatus = useRegShiftStore((state) => state.indexStatus);
  const setIndexStatus = useRegShiftStore((state) => state.setIndexStatus);
  const appendTrace = useRegShiftStore((state) => state.appendTrace);
  const setLoading = useRegShiftStore((state) => state.setLoading);
  const setError = useRegShiftStore((state) => state.setError);

  const handleScan = async () => {
    setLoading(true);
    setError(null);
    try {
      const status = await api.scanIndex();
      setIndexStatus(status);
      appendTrace([
        {
          timestamp: new Date().toISOString(),
          message: "Scanned ERPNext code index",
          status: "completed",
          explanation: `${status.file_count} files indexed from ${status.source}`,
          evidence_count: status.file_count,
        },
      ]);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Scan failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <header className="flex items-center justify-between border-b border-[#e8e4df] bg-white/80 px-6 py-4 backdrop-blur-xl">
      <div className="flex items-center gap-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-slate-500">RegShift</p>
          <h2 className="text-lg font-semibold">Conduct Extension Mode</h2>
        </div>
        <span className="rounded-full border border-orange-200 bg-gradient-to-r from-orange-50 to-red-50 px-3 py-1 text-xs font-medium text-orange-700">
          Conduct Extension Mode
        </span>
      </div>
      <div className="flex items-center gap-4">
        <BackendStatusBadge />
        <div className="text-right">
          <p className="text-xs uppercase tracking-wider text-slate-500">System Context</p>
          <p className="text-sm font-medium">ERPNext</p>
        </div>
        <div
          data-testid="repo-status"
          className="rounded-full border border-[#e8e4df] bg-white px-3 py-1 text-xs text-slate-600"
        >
          {indexStatus ? `${indexStatus.file_count} files · ${indexStatus.source}` : "Index not loaded"}
        </div>
        <button
          type="button"
          data-testid="scan-button"
          onClick={handleScan}
          className="glass-button flex items-center gap-2 rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium shadow-sm transition hover:shadow-md"
        >
          <RefreshCw size={16} />
          Scan
        </button>
      </div>
    </header>
  );
}

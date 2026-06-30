"use client";

import { useRegShiftStore } from "@/lib/store";
import type { BackendConnectionStatus } from "@/lib/types";

const STATUS_LABELS: Record<BackendConnectionStatus, string> = {
  checking: "Checking API…",
  online: "API online",
  offline: "API unreachable",
};

const STATUS_STYLES: Record<BackendConnectionStatus, string> = {
  checking: "border-amber-200 bg-amber-50 text-amber-700",
  online: "border-emerald-200 bg-emerald-50 text-emerald-700",
  offline: "border-red-200 bg-red-50 text-red-700",
};

export function BackendStatusBadge() {
  const backendStatus = useRegShiftStore((state) => state.backendStatus);

  return (
    <div
      data-testid="backend-status"
      className={`rounded-full border px-3 py-1 text-xs font-medium ${STATUS_STYLES[backendStatus]}`}
    >
      {STATUS_LABELS[backendStatus]}
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useRegShiftStore } from "@/lib/store";
import type { DomainPackSummary } from "@/lib/types";

export function DomainPacksView() {
  const backendStatus = useRegShiftStore((state) => state.backendStatus);
  const [packs, setPacks] = useState<DomainPackSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (backendStatus === "offline") {
      setIsLoading(false);
      setError("Backend is unreachable. Cannot load domain packs.");
      return;
    }
    if (backendStatus === "checking") {
      return;
    }

    setIsLoading(true);
    setError(null);
    api
      .listDomainPacks()
      .then((response) => setPacks(response.packs))
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "Failed to load domain packs");
      })
      .finally(() => setIsLoading(false));
  }, [backendStatus]);

  return (
    <div data-testid="domain-packs-view" className="mx-auto flex max-w-7xl flex-col gap-6">
      <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Domain Packs</p>
        <h2 className="mt-2 text-2xl font-semibold">Configured assurance domains</h2>
        <p className="mt-2 text-sm text-slate-600">
          Domain packs define processes, modules, and rules used during classification and impact tracing.
        </p>
      </section>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      ) : null}

      {isLoading ? <p className="text-sm text-slate-500">Loading domain packs…</p> : null}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {packs.map((pack) => (
          <article
            key={pack.domain}
            data-testid={`domain-pack-${pack.domain}`}
            className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-5 shadow-sm"
          >
            <p className="text-xs uppercase tracking-wider text-slate-500">{pack.domain}</p>
            <h3 className="mt-1 text-lg font-semibold">{pack.display_name}</h3>
            <p className="mt-2 text-sm text-slate-600">{pack.description}</p>
            <div className="mt-4 flex gap-3 text-xs text-slate-500">
              <span>{pack.process_count} processes</span>
              <span>{pack.module_count} modules</span>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

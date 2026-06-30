"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useRegShiftStore } from "@/lib/store";
import type { DashboardStats } from "@/lib/types";

function MetricCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4">
      <p className="text-xs uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      {sub ? <p className="mt-1 text-xs text-slate-500">{sub}</p> : null}
    </div>
  );
}

function BarChart({ items }: { items: { label: string; value: number }[] }) {
  const maxValue = Math.max(...items.map((item) => item.value), 1);
  return (
    <div className="space-y-3">
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">No session data yet.</p>
      ) : (
        items.map((item) => (
          <div key={item.label}>
            <div className="mb-1 flex items-center justify-between text-xs">
              <span className="font-medium capitalize">{item.label}</span>
              <span className="text-slate-500">{item.value}</span>
            </div>
            <div className="h-2 rounded-full bg-slate-100">
              <div
                className="h-2 rounded-full bg-gradient-to-r from-orange-500 to-red-500"
                style={{ width: `${(item.value / maxValue) * 100}%` }}
              />
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function FunnelChart({ stats }: { stats: DashboardStats }) {
  const stages = [
    { label: "Sessions", value: stats.total_sessions },
    { label: "Contracts", value: stats.sessions_with_contracts },
    { label: "Approved", value: stats.approved_contracts },
    { label: "Change packs", value: stats.change_packs },
  ];
  const maxValue = Math.max(...stages.map((stage) => stage.value), 1);

  return (
    <div className="grid gap-3 md:grid-cols-4">
      {stages.map((stage) => (
        <div key={stage.label} className="rounded-xl border border-[#e8e4df] bg-white p-4 text-center">
          <p className="text-xs uppercase tracking-wider text-slate-500">{stage.label}</p>
          <p className="mt-2 text-3xl font-semibold">{stage.value}</p>
          <div className="mx-auto mt-3 h-24 w-4 rounded-full bg-slate-100">
            <div
              className="w-4 rounded-full bg-gradient-to-t from-orange-500 to-red-400"
              style={{ height: `${Math.max((stage.value / maxValue) * 100, 8)}%`, marginTop: "auto" }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function DashboardOverview() {
  const backendStatus = useRegShiftStore((state) => state.backendStatus);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (backendStatus === "offline") {
      setIsLoading(false);
      setError("Backend is unreachable. Dashboard metrics cannot load.");
      return;
    }
    if (backendStatus === "checking") {
      return;
    }

    setIsLoading(true);
    setError(null);
    api
      .getDashboardStats()
      .then(setStats)
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "Failed to load dashboard");
      })
      .finally(() => setIsLoading(false));
  }, [backendStatus]);

  return (
    <div data-testid="dashboard-overview" className="mx-auto flex max-w-7xl flex-col gap-6">
      <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Overview</p>
        <h2 className="mt-2 text-2xl font-semibold">Change assurance metrics</h2>
        <p className="mt-2 text-sm text-slate-600">
          Live stats from sessions, contracts, indexed code, and domain packs.
        </p>
      </section>

      {error ? (
        <div data-testid="dashboard-error" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {isLoading ? (
        <p className="text-sm text-slate-500" data-testid="dashboard-loading">
          Loading dashboard…
        </p>
      ) : null}

      {stats ? (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Total sessions" value={stats.total_sessions} />
            <MetricCard label="Indexed files" value={stats.indexed_files} sub={stats.index_source} />
            <MetricCard label="Active policies" value={stats.active_policies} />
            <MetricCard label="Domain packs" value={stats.domain_packs} sub={`Graph: ${stats.graph_backend}`} />
          </div>

          <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
            <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Workflow funnel</p>
            <FunnelChart stats={stats} />
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
              <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Sessions by domain</p>
              <BarChart
                items={stats.sessions_by_domain.map((item) => ({
                  label: item.domain,
                  value: item.count,
                }))}
              />
            </section>
            <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
              <p className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-500">Assurance coverage</p>
              <BarChart
                items={[
                  { label: "With contracts", value: stats.sessions_with_contracts },
                  { label: "Approved", value: stats.approved_contracts },
                  { label: "Packs generated", value: stats.change_packs },
                ]}
              />
            </section>
          </div>
        </>
      ) : null}
    </div>
  );
}

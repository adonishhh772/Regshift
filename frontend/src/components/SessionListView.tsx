"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useRegShiftStore } from "@/lib/store";
import type { SessionSummary } from "@/lib/types";

interface SessionListViewProps {
  title: string;
  description: string;
  filter: "contracts" | "change-packs" | "all";
}

function filterSessions(sessions: SessionSummary[], filter: SessionListViewProps["filter"]): SessionSummary[] {
  if (filter === "contracts") {
    return sessions.filter((session) => session.has_contract);
  }
  if (filter === "change-packs") {
    return sessions.filter((session) => Boolean(session.pack_id));
  }
  return sessions;
}

export function SessionListView({ title, description, filter }: SessionListViewProps) {
  const router = useRouter();
  const backendStatus = useRegShiftStore((state) => state.backendStatus);
  const setPack = useRegShiftStore((state) => state.setPack);
  const setSession = useRegShiftStore((state) => state.setSession);
  const setContract = useRegShiftStore((state) => state.setContract);
  const setStoreError = useRegShiftStore((state) => state.setError);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingPackId, setLoadingPackId] = useState<string | null>(null);

  const handleOpenPack = async (packId: string) => {
    setLoadingPackId(packId);
    setError(null);
    try {
      const loaded = await api.loadPack(packId);
      setSession(loaded.session_id, loaded.domain ?? "procurement", 1);
      setPack(loaded.markdown, loaded.filename);
      if (loaded.contract_yaml) {
        setContract(loaded.contract_yaml, true);
      }
      router.push("/demo");
    } catch (loadError) {
      const message = loadError instanceof Error ? loadError.message : "Failed to load change pack";
      setError(message);
      setStoreError(message);
    } finally {
      setLoadingPackId(null);
    }
  };

  useEffect(() => {
    if (backendStatus === "offline") {
      setIsLoading(false);
      setError("Backend is unreachable. Cannot load sessions.");
      return;
    }
    if (backendStatus === "checking") {
      return;
    }

    setIsLoading(true);
    setError(null);
    api
      .listSessions()
      .then((response) => setSessions(filterSessions(response.sessions, filter)))
      .catch((loadError) => {
        setError(loadError instanceof Error ? loadError.message : "Failed to load sessions");
      })
      .finally(() => setIsLoading(false));
  }, [backendStatus, filter]);

  return (
    <div data-testid={`session-list-${filter}`} className="mx-auto flex max-w-7xl flex-col gap-6">
      <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{title}</p>
        <h2 className="mt-2 text-2xl font-semibold">{title}</h2>
        <p className="mt-2 text-sm text-slate-600">{description}</p>
      </section>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
      ) : null}

      {isLoading ? <p className="text-sm text-slate-500">Loading…</p> : null}

      {!isLoading && sessions.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#e8e4df] bg-white p-6 text-sm text-slate-600">
          No items yet. Use Chat or Demo Workflow to create a session.
        </div>
      ) : null}

      <div className="grid gap-4">
        {sessions.map((session) => (
          <article
            key={session.id}
            data-testid={`session-row-${session.id}`}
            className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-5 shadow-sm"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs uppercase tracking-wider text-slate-500">{session.domain ?? "unclassified"}</p>
                <p className="mt-1 text-sm font-medium">{session.business_text}</p>
              </div>
              <div className="text-right text-xs text-slate-500">
                <p>{new Date(session.created_at).toLocaleString()}</p>
                <p className="mt-1 font-mono">{session.id.slice(0, 8)}…</p>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {session.has_contract ? (
                <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-blue-700">
                  Contract
                </span>
              ) : null}
              {session.contract_approved ? (
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
                  Approved
                </span>
              ) : null}
              {session.pack_id ? (
                <span className="rounded-full border border-orange-200 bg-orange-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-orange-700">
                  Pack
                </span>
              ) : null}
            </div>
            {session.pack_id ? (
              <button
                type="button"
                data-testid={`open-pack-${session.id}`}
                disabled={loadingPackId === session.pack_id}
                onClick={() => handleOpenPack(session.pack_id ?? "")}
                className="mt-4 rounded-xl bg-gradient-to-r from-teal-500 to-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:opacity-50"
              >
                {loadingPackId === session.pack_id ? "Loading…" : "Open & Implement"}
              </button>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}

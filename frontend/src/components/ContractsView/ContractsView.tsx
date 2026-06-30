"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, Copy, ExternalLink, FileText, Loader2 } from "lucide-react";

import { api } from "@/lib/api";
import { normalizeFetchError } from "@/lib/networkErrors";
import { useRegShiftStore } from "@/lib/store";
import type { SessionDetail, SessionSummary } from "@/lib/types";

function formatDomainLabel(domain: string | null | undefined): string {
  if (!domain) {
    return "Unclassified";
  }
  return domain.replace(/_/g, " ");
}

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}…`;
}

function readStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string");
}

function readStringMap(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object") {
    return {};
  }
  const entries = Object.entries(value as Record<string, unknown>).filter(
    (entry): entry is [string, string] => typeof entry[1] === "string"
  );
  return Object.fromEntries(entries);
}

interface ContractSummaryProps {
  contract: Record<string, unknown>;
}

function ContractSummary({ contract }: ContractSummaryProps) {
  const entity = typeof contract.entity === "string" ? contract.entity : null;
  const trigger = contract.trigger;
  const obligations = readStringList(contract.required_behaviour);
  const approvalRoles = readStringList(contract.approval_roles);
  const risks = readStringMap(contract.risks);
  const triggerCondition =
    trigger && typeof trigger === "object" && typeof (trigger as Record<string, unknown>).condition === "string"
      ? String((trigger as Record<string, unknown>).condition)
      : null;

  return (
    <div className="grid gap-4 sm:grid-cols-2" data-testid="contract-summary">
      {entity ? (
        <div className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Entity</p>
          <p className="mt-1 text-sm font-medium text-slate-900">{entity.replace(/_/g, " ")}</p>
        </div>
      ) : null}
      {triggerCondition ? (
        <div className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Trigger</p>
          <p className="mt-1 font-mono text-sm text-slate-800">{triggerCondition}</p>
        </div>
      ) : null}
      {obligations.length > 0 ? (
        <div className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4 sm:col-span-2">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Obligations</p>
          <ul className="mt-2 space-y-1.5">
            {obligations.map((obligation) => (
              <li key={obligation} className="flex items-start gap-2 text-sm text-slate-700">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" />
                <span>{obligation.replace(/_/g, " ")}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {approvalRoles.length > 0 ? (
        <div className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Approval roles</p>
          <ul className="mt-2 space-y-1 text-sm text-slate-700">
            {approvalRoles.map((role) => (
              <li key={role}>{role}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {Object.keys(risks).length > 0 ? (
        <div className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Risks</p>
          <ul className="mt-2 space-y-1 text-sm text-slate-700">
            {Object.entries(risks).map(([riskName, level]) => (
              <li key={riskName} className="flex justify-between gap-3">
                <span>{riskName.replace(/_/g, " ")}</span>
                <span className="font-medium capitalize text-slate-900">{level}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

export function ContractsView() {
  const router = useRouter();
  const backendStatus = useRegShiftStore((state) => state.backendStatus);
  const setSession = useRegShiftStore((state) => state.setSession);
  const setContract = useRegShiftStore((state) => state.setContract);
  const setChangeText = useRegShiftStore((state) => state.setChangeText);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [sessionDetail, setSessionDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copyMessage, setCopyMessage] = useState<string | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);

  const selectedSummary = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? null,
    [sessions, selectedSessionId]
  );

  const loadSessions = useCallback(async () => {
    setIsLoadingList(true);
    setError(null);
    try {
      const response = await api.listSessions();
      const contractSessions = response.sessions.filter((session) => session.has_contract);
      setSessions(contractSessions);
      setSelectedSessionId((current) => {
        if (current && contractSessions.some((session) => session.id === current)) {
          return current;
        }
        return contractSessions[0]?.id ?? null;
      });
    } catch (loadError) {
      setError(normalizeFetchError(loadError));
      setSessions([]);
      setSelectedSessionId(null);
    } finally {
      setIsLoadingList(false);
    }
  }, []);

  useEffect(() => {
    if (backendStatus === "offline") {
      setIsLoadingList(false);
      setError("Backend is unreachable. Cannot load contracts.");
      return;
    }
    if (backendStatus === "checking") {
      return;
    }
    loadSessions().catch(() => undefined);
  }, [backendStatus, loadSessions]);

  useEffect(() => {
    if (!selectedSessionId) {
      setSessionDetail(null);
      return;
    }
    setIsLoadingDetail(true);
    setError(null);
    api
      .getSession(selectedSessionId)
      .then((detail) => setSessionDetail(detail))
      .catch((loadError) => {
        setError(normalizeFetchError(loadError));
        setSessionDetail(null);
      })
      .finally(() => setIsLoadingDetail(false));
  }, [selectedSessionId]);

  const handleSelectSession = useCallback((sessionId: string) => {
    setSelectedSessionId(sessionId);
    setCopyMessage(null);
  }, []);

  const handleCopyYaml = useCallback(async () => {
    if (!sessionDetail?.contract_yaml) {
      return;
    }
    try {
      await navigator.clipboard.writeText(sessionDetail.contract_yaml);
      setCopyMessage("Contract YAML copied to clipboard.");
    } catch {
      setCopyMessage("Could not copy to clipboard.");
    }
  }, [sessionDetail?.contract_yaml]);

  const handleOpenInDemo = useCallback(() => {
    if (!sessionDetail?.contract_yaml) {
      return;
    }
    setChangeText(sessionDetail.business_text);
    setSession(sessionDetail.id, sessionDetail.domain ?? "procurement", 1);
    setContract(sessionDetail.contract_yaml, sessionDetail.contract_approved);
    router.push("/demo");
  }, [router, sessionDetail, setChangeText, setContract, setSession]);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6" data-testid="contracts-view">
      <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Change Contracts</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">Contract library</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          Browse compiled change contracts from workflow sessions. Select a contract to read obligations, approval
          roles, and the full YAML definition.
        </p>
      </section>

      {error ? (
        <div className="rounded-xl border border-pink-200 bg-pink-50 px-4 py-3 text-sm text-pink-800" data-testid="contracts-error">
          {error}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-4 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-900">Sessions</h2>
            <span className="rounded-full bg-[#FAF9F7] px-2 py-0.5 text-xs text-slate-600">{sessions.length}</span>
          </div>

          {isLoadingList ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading contracts…
            </div>
          ) : null}

          {!isLoadingList && sessions.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#e8e4df] bg-[#FAF9F7] p-4 text-sm text-slate-600">
              No contracts yet. Use Chat or Demo Workflow to compile a change contract.
            </div>
          ) : null}

          <ul className="space-y-2">
            {sessions.map((session) => {
              const isSelected = session.id === selectedSessionId;
              return (
                <li key={session.id}>
                  <button
                    type="button"
                    data-testid={`contract-session-${session.id}`}
                    onClick={() => handleSelectSession(session.id)}
                    className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                      isSelected
                        ? "border-purple-200 bg-purple-50 shadow-sm"
                        : "border-[#e8e4df] bg-white hover:bg-[#FAF9F7]"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <FileText className={`mt-0.5 h-4 w-4 shrink-0 ${isSelected ? "text-purple-600" : "text-slate-400"}`} />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs uppercase tracking-wider text-slate-500">
                          {formatDomainLabel(session.domain)}
                        </p>
                        <p className="mt-1 text-sm font-medium text-slate-900">
                          {truncateText(session.business_text, 72)}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {session.contract_approved ? (
                            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
                              Approved
                            </span>
                          ) : (
                            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-700">
                              Draft
                            </span>
                          )}
                        </div>
                        <p className="mt-2 text-[10px] text-slate-500">{new Date(session.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>

        <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
          {!selectedSummary ? (
            <div className="rounded-xl border border-dashed border-[#e8e4df] bg-[#FAF9F7] p-8 text-center text-sm text-slate-600">
              Select a contract from the list to view its details.
            </div>
          ) : null}

          {selectedSummary && isLoadingDetail ? (
            <div className="flex items-center gap-2 text-sm text-slate-500" data-testid="contracts-detail-loading">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading contract…
            </div>
          ) : null}

          {sessionDetail && !isLoadingDetail ? (
            <div data-testid="contract-detail">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                    {formatDomainLabel(sessionDetail.domain)}
                  </p>
                  <h2 className="mt-2 text-lg font-semibold text-slate-900">Change contract</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{sessionDetail.business_text}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {sessionDetail.contract_approved ? (
                    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
                      Approved
                    </span>
                  ) : (
                    <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                      Awaiting approval
                    </span>
                  )}
                </div>
              </div>

              {sessionDetail.contract ? (
                <div className="mt-6">
                  <ContractSummary contract={sessionDetail.contract} />
                </div>
              ) : null}

              <div className="mt-6 flex flex-wrap gap-2">
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-[#FAF9F7]"
                  data-testid="copy-contract-yaml"
                  onClick={handleCopyYaml}
                >
                  <Copy className="h-4 w-4" />
                  Copy YAML
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-xl border border-purple-200 bg-purple-50 px-4 py-2 text-sm font-medium text-purple-700 shadow-sm hover:bg-purple-100"
                  data-testid="open-contract-in-demo"
                  onClick={handleOpenInDemo}
                >
                  <ExternalLink className="h-4 w-4" />
                  Open in Demo Workflow
                </button>
              </div>

              {copyMessage ? <p className="mt-3 text-xs text-emerald-700">{copyMessage}</p> : null}

              {sessionDetail.contract_yaml ? (
                <div className="mt-6">
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Contract YAML</p>
                  <pre
                    className="mt-2 max-h-[420px] overflow-auto rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4 font-mono text-xs leading-relaxed text-slate-800"
                    data-testid="contract-yaml-view"
                  >
                    {sessionDetail.contract_yaml}
                  </pre>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}

export default ContractsView;

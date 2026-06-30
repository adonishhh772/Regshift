"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Archive, CheckCircle2, FolderOpen, RefreshCw } from "lucide-react";

import { PolicyRulesList } from "@/components/PolicyRulesList";
import { api } from "@/lib/api";
import { normalizeFetchError } from "@/lib/networkErrors";
import { getPolicyRuleCount, getPolicyRules } from "@/lib/policyRules";
import type { PolicyDocument } from "@/lib/types";

const POLICY_STATUS_ACTIVE = "active";
const POLICY_STATUS_ARCHIVED = "archived";

interface PolicyStorePanelProps {
  refreshKey?: number;
  onPolicyActivated?: (policy: PolicyDocument) => void;
  onPolicySelected?: (policy: PolicyDocument | null) => void;
  embedded?: boolean;
}

function getPanelSurfaceClassName(embedded: boolean): string {
  return embedded ? "p-2" : "glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm";
}

function formatDomainLabel(domain: string | null): string {
  if (!domain) {
    return "Global";
  }
  return domain.replace(/_/g, " ");
}

function formatPolicyDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function PolicyStorePanel({
  refreshKey = 0,
  onPolicyActivated,
  onPolicySelected,
  embedded = false,
}: PolicyStorePanelProps) {
  const [policies, setPolicies] = useState<PolicyDocument[]>([]);
  const [activeDomains, setActiveDomains] = useState<string[]>([]);
  const [domainFilter, setDomainFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedPolicyId, setSelectedPolicyId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isActivating, setIsActivating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadPolicies = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const response = await api.listPolicies();
      setPolicies(response.policies);
      setActiveDomains(response.active_domains);
      setSelectedPolicyId((current) => {
        if (response.policies.length === 0) {
          return null;
        }
        if (current && response.policies.some((policy) => policy.id === current)) {
          return current;
        }
        return null;
      });
    } catch (error) {
      setErrorMessage(normalizeFetchError(error));
      setPolicies([]);
      setActiveDomains([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPolicies().catch(() => undefined);
  }, [loadPolicies, refreshKey]);

  const domainOptions = useMemo(() => {
    const domains = new Set<string>();
    policies.forEach((policy) => {
      if (policy.domain) {
        domains.add(policy.domain);
      }
    });
    return Array.from(domains).sort();
  }, [policies]);

  const filteredPolicies = useMemo(() => {
    return policies.filter((policy) => {
      const matchesDomain = domainFilter === "all" || policy.domain === domainFilter;
      const matchesStatus = statusFilter === "all" || policy.status === statusFilter;
      return matchesDomain && matchesStatus;
    });
  }, [domainFilter, policies, statusFilter]);

  const selectedPolicy = useMemo(() => {
    if (!selectedPolicyId) {
      return null;
    }
    return policies.find((policy) => policy.id === selectedPolicyId) ?? null;
  }, [policies, selectedPolicyId]);

  const handleSelectPolicy = (policyId: string) => {
    setSelectedPolicyId((current) => {
      const nextId = current === policyId ? null : policyId;
      const nextPolicy = nextId ? policies.find((policy) => policy.id === nextId) ?? null : null;
      onPolicySelected?.(nextPolicy);
      return nextId;
    });
    setSuccessMessage(null);
  };

  const handleActivatePolicy = async (policyId: string, domain: string | null) => {
    if (!domain) {
      setErrorMessage("Policies without a domain cannot be activated.");
      return;
    }
    setIsActivating(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const result = await api.activatePolicy(policyId);
      setSuccessMessage(
        `Activated ${result.policy.title} for ${formatDomainLabel(domain)} (${result.node_count} graph nodes).`
      );
      await loadPolicies();
      setSelectedPolicyId(result.policy.id);
      onPolicySelected?.(result.policy);
      onPolicyActivated?.(result.policy);
    } catch (error) {
      setErrorMessage(normalizeFetchError(error));
    } finally {
      setIsActivating(false);
    }
  };

  const handleRefreshStore = () => {
    loadPolicies().catch(() => undefined);
  };

  return (
    <section
      data-testid="policy-store-panel"
      className={getPanelSurfaceClassName(embedded)}
    >
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-xl bg-blue-100 p-2 text-blue-600">
            <FolderOpen size={20} />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Policy Store</p>
            <h3 className="mt-1 text-lg font-semibold text-slate-900">Tenant policy library</h3>
            <p className="mt-1 max-w-2xl text-sm text-slate-600">
              Store multiple policies across domains. Each ingest adds a version; older versions stay in the store as
              archived. Activate any version to make it the governing policy for its domain.
            </p>
          </div>
        </div>
        <button
          type="button"
          data-testid="refresh-policy-store-button"
          disabled={isLoading}
          onClick={handleRefreshStore}
          className="flex items-center gap-2 rounded-xl border border-[#e8e4df] px-4 py-2 text-sm font-medium text-slate-700 disabled:opacity-50"
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      <div className="mb-4 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-[#FAF9F7] px-3 py-1">{policies.length} stored policies</span>
        <span className="rounded-full bg-emerald-100 px-3 py-1 font-medium text-emerald-700">
          {activeDomains.length} active domains
        </span>
      </div>

      <div className="mb-4 flex flex-wrap gap-3">
        <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Domain
          <select
            data-testid="policy-store-domain-filter"
            value={domainFilter}
            onChange={(event) => setDomainFilter(event.target.value)}
            className="glass-input rounded-xl border border-[#e8e4df] px-3 py-2 text-sm normal-case"
          >
            <option value="all">All domains</option>
            {domainOptions.map((domain) => (
              <option key={domain} value={domain}>
                {formatDomainLabel(domain)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Status
          <select
            data-testid="policy-store-status-filter"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
            className="glass-input rounded-xl border border-[#e8e4df] px-3 py-2 text-sm normal-case"
          >
            <option value="all">All statuses</option>
            <option value={POLICY_STATUS_ACTIVE}>Active</option>
            <option value={POLICY_STATUS_ARCHIVED}>Archived</option>
          </select>
        </label>
      </div>

      {errorMessage ? (
        <p data-testid="policy-store-error" className="mb-4 rounded-xl border border-pink-200 bg-pink-50 px-4 py-3 text-sm text-pink-800">
          {errorMessage}
        </p>
      ) : null}
      {successMessage ? (
        <p
          data-testid="policy-store-success"
          className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
        >
          {successMessage}
        </p>
      ) : null}

      {isLoading ? (
        <p data-testid="policy-store-loading" className="text-sm text-slate-500">
          Loading policy store…
        </p>
      ) : filteredPolicies.length === 0 ? (
        <div
          data-testid="policy-store-empty"
          className="rounded-xl border border-dashed border-[#e8e4df] bg-[#FAF9F7] px-6 py-10 text-center text-sm text-slate-500"
        >
          No policies in the store yet. Ingest a policy below to add the first one.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-[#e8e4df]">
          <table data-testid="policy-store-table" className="min-w-full text-left text-sm">
            <thead className="bg-[#FAF9F7] text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3 font-semibold">Title</th>
                <th className="px-4 py-3 font-semibold">Domain</th>
                <th className="px-4 py-3 font-semibold">Version</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Rules</th>
                <th className="px-4 py-3 font-semibold">Created</th>
                <th className="px-4 py-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredPolicies.map((policy) => {
                const isSelected = selectedPolicyId === policy.id;
                const isActive = policy.status === POLICY_STATUS_ACTIVE;
                return (
                  <tr
                    key={policy.id}
                    data-testid={`policy-store-row-${policy.id}`}
                    className={`border-t border-[#e8e4df] ${isSelected ? "bg-purple-50/60" : "bg-white"}`}
                  >
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        data-testid={`policy-store-select-${policy.id}`}
                        onClick={() => handleSelectPolicy(policy.id)}
                        className="text-left font-medium text-slate-900 hover:text-purple-700"
                      >
                        {policy.title}
                      </button>
                    </td>
                    <td className="px-4 py-3 capitalize text-slate-600">{formatDomainLabel(policy.domain)}</td>
                    <td className="px-4 py-3 text-slate-600">v{policy.version}</td>
                    <td className="px-4 py-3">
                      {isActive ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-700">
                          <CheckCircle2 size={12} />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
                          <Archive size={12} />
                          Archived
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{getPolicyRuleCount(policy)}</td>
                    <td className="px-4 py-3 text-slate-600">{formatPolicyDate(policy.created_at)}</td>
                    <td className="px-4 py-3">
                      {!isActive && policy.domain ? (
                        <button
                          type="button"
                          data-testid={`policy-store-activate-${policy.id}`}
                          disabled={isActivating}
                          onClick={() => handleActivatePolicy(policy.id, policy.domain)}
                          className="rounded-lg border border-purple-200 bg-purple-50 px-3 py-1 text-xs font-medium text-purple-700 disabled:opacity-50"
                        >
                          Set active
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selectedPolicy ? (
        <div
          data-testid="policy-store-detail"
          className="mt-4 space-y-4 rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4"
        >
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Selected policy</p>
            <p className="mt-2 text-sm font-medium text-slate-900">{selectedPolicy.title}</p>
            <p className="mt-1 text-xs text-slate-600">
              {formatDomainLabel(selectedPolicy.domain)} · v{selectedPolicy.version} ·{" "}
              {getPolicyRuleCount(selectedPolicy)} rules
            </p>
          </div>

          <PolicyRulesList rules={getPolicyRules(selectedPolicy)} maxHeightClassName="max-h-[360px]" />

          <div data-testid="policy-store-source-text">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Source document</p>
            <p className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-600">
              {selectedPolicy.source_text}
            </p>
          </div>
        </div>
      ) : null}
    </section>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { FileText, Shield, Upload } from "lucide-react";

import { api } from "@/lib/api";
import { DEMO_POLICY_TEXT } from "@/lib/demoPolicy";
import { useRegShiftStore } from "@/lib/store";
import type { GovernanceConfig, PolicyDocument, PolicyRule } from "@/lib/types";

interface PolicyPanelProps {
  onPolicyIngested?: () => void;
}

export function PolicyPanel({ onPolicyIngested }: PolicyPanelProps) {
  const domain = useRegShiftStore((state) => state.domain);
  const setActivePolicy = useRegShiftStore((state) => state.setActivePolicy);
  const setGovernanceConfig = useRegShiftStore((state) => state.setGovernanceConfig);
  const langfuseUiUrl = useRegShiftStore((state) => state.langfuseUiUrl);
  const isLoading = useRegShiftStore((state) => state.isLoading);
  const setLoading = useRegShiftStore((state) => state.setLoading);
  const setError = useRegShiftStore((state) => state.setError);
  const appendTrace = useRegShiftStore((state) => state.appendTrace);

  const [title, setTitle] = useState("ACME Corp Procurement Policy v2.1");
  const [policyText, setPolicyText] = useState(DEMO_POLICY_TEXT);
  const [policyDomain, setPolicyDomain] = useState("procurement");
  const [activePolicy, setLocalActivePolicy] = useState<PolicyDocument | null>(null);
  const [extractedRules, setExtractedRules] = useState<PolicyRule[]>([]);
  const [governanceConfig, setLocalGovernanceConfig] = useState<GovernanceConfig | null>(null);
  const [policyGraphNodes, setPolicyGraphNodes] = useState<number>(0);

  const loadActivePolicy = useCallback(async (targetDomain: string) => {
    try {
      const config = await api.getPolicyGovernance(targetDomain);
      setLocalGovernanceConfig(config);
      setGovernanceConfig(config);
      const graph = await api.getPolicyGraph(targetDomain);
      setPolicyGraphNodes(graph.nodes.length);
      if (config.configured) {
        const policy = await api.getActivePolicy(targetDomain);
        setLocalActivePolicy(policy);
        setActivePolicy(policy);
      }
    } catch {
      setLocalActivePolicy(null);
      setLocalGovernanceConfig(null);
      setPolicyGraphNodes(0);
    }
  }, [setActivePolicy, setGovernanceConfig]);

  useEffect(() => {
    const targetDomain = domain ?? "procurement";
    setPolicyDomain(targetDomain);
    loadActivePolicy(targetDomain).catch(() => undefined);
  }, [domain, loadActivePolicy]);

  const handleLoadDemoPolicy = () => {
    setTitle("ACME Corp Procurement Policy v2.1");
    setPolicyText(DEMO_POLICY_TEXT);
    setPolicyDomain("procurement");
  };

  const handleIngestPolicy = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.ingestPolicy({
        title,
        source_text: policyText,
        domain: policyDomain,
      });
      setLocalActivePolicy(result.policy);
      setExtractedRules(result.extracted_rules);
      setActivePolicy(result.policy);
      appendTrace(result.trace);
      const config = await api.getPolicyGovernance(result.policy.domain ?? policyDomain);
      setLocalGovernanceConfig(config);
      setGovernanceConfig(config);
      onPolicyIngested?.();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Policy ingestion failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section data-testid="policy-panel" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-purple-100 p-2 text-purple-600">
            <Shield size={20} />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Tenant Policy</p>
            <p className="mt-1 text-sm text-slate-600">Ingest business policy to drive governance and agent evaluation</p>
          </div>
        </div>
        <button
          type="button"
          data-testid="load-demo-policy-button"
          onClick={handleLoadDemoPolicy}
          className="glass-button rounded-xl border border-[#e8e4df] px-4 py-2 text-sm font-medium text-slate-700"
        >
          Load Demo Policy
        </button>
      </div>

      <div className="mb-4 flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-[#FAF9F7] px-3 py-1">Knowledge graph: {policyGraphNodes} policy nodes</span>
        {langfuseUiUrl ? (
          <a
            href={langfuseUiUrl}
            target="_blank"
            rel="noreferrer"
            data-testid="langfuse-link"
            className="rounded-full bg-purple-100 px-3 py-1 font-medium text-purple-700 hover:bg-purple-200"
          >
            Open Langfuse traces
          </a>
        ) : null}
      </div>

      {activePolicy ? (
        <div data-testid="active-policy-banner" className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          Active: {activePolicy.title} (v{activePolicy.version}) — {activePolicy.rules.rule_count ?? extractedRules.length} rules governing{" "}
          {activePolicy.domain}
        </div>
      ) : (
        <div data-testid="no-policy-banner" className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          No tenant policy ingested for this domain. Ingest your business policy before compiling contracts.
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500" htmlFor="policy-title">
            Policy Title
          </label>
          <input
            id="policy-title"
            data-testid="policy-title-input"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            className="glass-input w-full rounded-xl border border-[#e8e4df] px-4 py-2 text-sm"
          />
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500" htmlFor="policy-domain">
            Domain
          </label>
          <select
            id="policy-domain"
            data-testid="policy-domain-select"
            value={policyDomain}
            onChange={(event) => setPolicyDomain(event.target.value)}
            className="glass-input w-full rounded-xl border border-[#e8e4df] px-4 py-2 text-sm"
          >
            <option value="procurement">Procurement</option>
            <option value="inventory">Inventory</option>
            <option value="finance_billing">Finance / Billing</option>
            <option value="hr_compliance">HR / Compliance</option>
            <option value="security">Security</option>
          </select>
          <label className="block text-xs font-semibold uppercase tracking-wider text-slate-500" htmlFor="policy-text">
            Policy Document
          </label>
          <textarea
            id="policy-text"
            data-testid="policy-text-input"
            value={policyText}
            onChange={(event) => setPolicyText(event.target.value)}
            rows={12}
            className="glass-input w-full rounded-xl border border-[#e8e4df] px-4 py-3 font-mono text-xs leading-relaxed"
          />
          <button
            type="button"
            data-testid="ingest-policy-button"
            disabled={isLoading || policyText.length < 20}
            onClick={handleIngestPolicy}
            className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:opacity-50"
          >
            <Upload size={16} />
            Ingest Policy
          </button>
        </div>

        <div className="space-y-3">
          {governanceConfig?.configured ? (
            <GovernanceConfigSummary config={governanceConfig} />
          ) : null}
          {extractedRules.length > 0 ? (
            <PolicyRulesList rules={extractedRules} />
          ) : activePolicy?.rules?.rules ? (
            <PolicyRulesList rules={activePolicy.rules.rules as PolicyRule[]} />
          ) : (
            <div className="flex h-full min-h-[200px] flex-col items-center justify-center rounded-xl border border-dashed border-[#e8e4df] bg-[#FAF9F7] p-6 text-center">
              <FileText className="mb-2 text-slate-400" size={32} />
              <p className="text-sm text-slate-500">Extracted governance rules will appear here after ingestion</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function GovernanceConfigSummary({ config }: { config: GovernanceConfig }) {
  return (
    <div data-testid="governance-config-summary" className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Governance Layer</p>
      <p className="mt-2 text-sm font-medium">{config.policy_title}</p>
      <dl className="mt-3 space-y-2 text-xs text-slate-600">
        {config.threshold !== null && config.threshold !== undefined ? (
          <div className="flex justify-between">
            <dt>Approval threshold</dt>
            <dd className="font-medium text-slate-900">£{config.threshold.toLocaleString()}</dd>
          </div>
        ) : null}
        <div>
          <dt className="mb-1">Obligations</dt>
          <dd className="flex flex-wrap gap-1">
            {config.obligations.map((obligation) => (
              <span key={obligation} className="rounded-full bg-purple-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-purple-700">
                {obligation.replace(/_/g, " ")}
              </span>
            ))}
          </dd>
        </div>
        <div>
          <dt className="mb-1">Approval roles</dt>
          <dd>{config.approval_roles.join(", ") || "—"}</dd>
        </div>
      </dl>
    </div>
  );
}

function PolicyRulesList({ rules }: { rules: PolicyRule[] }) {
  return (
    <div data-testid="policy-rules-list" className="max-h-[420px] space-y-2 overflow-y-auto">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
        Extracted Rules ({rules.length})
      </p>
      {rules.map((rule) => (
        <div
          key={rule.id}
          data-testid={`policy-rule-${rule.id}`}
          className="rounded-xl border border-[#e8e4df] bg-white px-4 py-3"
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium">{rule.description}</p>
            <span className="shrink-0 rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-blue-700">
              {rule.type}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">{rule.citation}</p>
        </div>
      ))}
    </div>
  );
}

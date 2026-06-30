"use client";

import { useEffect, useState } from "react";
import { Upload } from "lucide-react";

import { api } from "@/lib/api";
import { DEMO_POLICY_TEXT } from "@/lib/demoPolicy";
import { normalizeFetchError } from "@/lib/networkErrors";
import { useRegShiftStore } from "@/lib/store";

interface PolicyPanelProps {
  onPolicyIngested?: () => void;
  onDomainChange?: (domain: string) => void;
  showDemoLoader?: boolean;
  embedded?: boolean;
}

export function PolicyPanel({
  onPolicyIngested,
  onDomainChange,
  showDemoLoader = false,
  embedded = false,
}: PolicyPanelProps) {
  const domain = useRegShiftStore((state) => state.domain);
  const setActivePolicy = useRegShiftStore((state) => state.setActivePolicy);
  const setGovernanceConfig = useRegShiftStore((state) => state.setGovernanceConfig);
  const isLoading = useRegShiftStore((state) => state.isLoading);
  const setLoading = useRegShiftStore((state) => state.setLoading);
  const appendTrace = useRegShiftStore((state) => state.appendTrace);
  const bumpWorkflowTraceVersion = useRegShiftStore((state) => state.bumpWorkflowTraceVersion);

  const [title, setTitle] = useState(showDemoLoader ? "ACME Corp Procurement Policy v2.1" : "");
  const [policyText, setPolicyText] = useState(showDemoLoader ? DEMO_POLICY_TEXT : "");
  const [policyDomain, setPolicyDomain] = useState("procurement");
  const [ingestError, setIngestError] = useState<string | null>(null);

  useEffect(() => {
    const targetDomain = domain ?? "procurement";
    setPolicyDomain(targetDomain);
    onDomainChange?.(targetDomain);
  }, [domain, onDomainChange]);

  const handleLoadDemoPolicy = () => {
    setTitle("ACME Corp Procurement Policy v2.1");
    setPolicyText(DEMO_POLICY_TEXT);
    setPolicyDomain("procurement");
    onDomainChange?.("procurement");
  };

  const handleDomainChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const nextDomain = event.target.value;
    setPolicyDomain(nextDomain);
    onDomainChange?.(nextDomain);
  };

  const handleIngestPolicy = async () => {
    setLoading(true);
    setIngestError(null);
    try {
      const result = await api.ingestPolicy({
        title,
        source_text: policyText,
        domain: policyDomain,
      });
      setActivePolicy(result.policy);
      appendTrace(result.trace);
      bumpWorkflowTraceVersion();
      const config = await api.getPolicyGovernance(result.policy.domain ?? policyDomain);
      setGovernanceConfig(config);
      setTitle("");
      setPolicyText("");
      onPolicyIngested?.();
    } catch (error) {
      setIngestError(normalizeFetchError(error));
    } finally {
      setLoading(false);
    }
  };

  const handlePolicyFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const content = typeof reader.result === "string" ? reader.result : "";
      setPolicyText(content);
      if (!title) {
        setTitle(file.name.replace(/\.[^.]+$/, "").replace(/[_-]/g, " "));
      }
    };
    reader.readAsText(file);
    event.target.value = "";
  };

  return (
    <section
      data-testid="policy-panel"
      className={embedded ? "p-2" : "glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm"}
    >
      <div className="mx-auto max-w-2xl space-y-4">
        {showDemoLoader ? (
          <div className="flex justify-end">
            <button
              type="button"
              data-testid="load-demo-policy-button"
              onClick={handleLoadDemoPolicy}
              className="glass-button rounded-xl border border-[#e8e4df] px-4 py-2 text-sm font-medium text-slate-700"
            >
              Load Demo Policy
            </button>
          </div>
        ) : null}

        {ingestError ? (
          <p
            data-testid="policy-ingest-error"
            className="rounded-xl border border-pink-200 bg-pink-50 px-4 py-3 text-sm text-pink-800"
          >
            {ingestError}
          </p>
        ) : null}

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
          onChange={handleDomainChange}
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
        <label
          htmlFor="policy-file-upload"
          className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-[#e8e4df] bg-[#FAF9F7] px-4 py-3 text-sm text-slate-600 transition hover:border-purple-200"
        >
          <Upload size={16} />
          Upload policy file (.txt, .md)
          <input
            id="policy-file-upload"
            data-testid="policy-file-upload"
            type="file"
            accept=".txt,.md,.text"
            onChange={handlePolicyFileUpload}
            className="sr-only"
          />
        </label>
        <textarea
          id="policy-text"
          data-testid="policy-text-input"
          value={policyText}
          onChange={(event) => setPolicyText(event.target.value)}
          rows={14}
          placeholder="Paste or upload your organisation's policy document…"
          className="glass-input w-full rounded-xl border border-[#e8e4df] px-4 py-3 font-mono text-xs leading-relaxed"
        />

        <button
          type="button"
          data-testid="ingest-policy-button"
          disabled={isLoading || policyText.length < 20 || title.trim().length < 3}
          onClick={handleIngestPolicy}
          className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:opacity-50"
        >
          <Upload size={16} />
          {isLoading ? "Ingesting…" : "Ingest"}
        </button>
      </div>
    </section>
  );
}

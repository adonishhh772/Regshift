"use client";

import { useState } from "react";

import { PolicyGraphPanel } from "@/components/PolicyGraphPanel";
import { PolicyPanel } from "@/components/PolicyPanel";
import { PolicyStorePanel } from "@/components/PolicyStorePanel";
import { api } from "@/lib/api";
import type { PolicyDocument } from "@/lib/types";

const POLICY_TAB_STORE = "store";
const POLICY_TAB_INGEST = "ingest";

type PolicyTabId = typeof POLICY_TAB_STORE | typeof POLICY_TAB_INGEST;

const POLICY_TABS: ReadonlyArray<{ id: PolicyTabId; label: string; testId: string }> = [
  { id: POLICY_TAB_STORE, label: "Policy Store", testId: "policies-tab-store" },
  { id: POLICY_TAB_INGEST, label: "Ingest", testId: "policies-tab-ingest" },
];

export function PoliciesView() {
  const [activeTab, setActiveTab] = useState<PolicyTabId>(POLICY_TAB_STORE);
  const [selectedGraphPolicy, setSelectedGraphPolicy] = useState<PolicyDocument | null>(null);
  const [storeRefreshKey, setStoreRefreshKey] = useState(0);
  const [graphRefreshKey, setGraphRefreshKey] = useState(0);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [rebuildMessage, setRebuildMessage] = useState<string | null>(null);

  const handlePolicyIngested = () => {
    setStoreRefreshKey((current) => current + 1);
    setSelectedGraphPolicy(null);
    setRebuildMessage(null);
    setActiveTab(POLICY_TAB_STORE);
  };

  const handlePolicySelected = (policy: PolicyDocument | null) => {
    setSelectedGraphPolicy(policy);
    if (policy) {
      setGraphRefreshKey((current) => current + 1);
    }
    setRebuildMessage(null);
  };

  const handlePolicyActivated = (policy: PolicyDocument) => {
    setSelectedGraphPolicy(policy);
    setGraphRefreshKey((current) => current + 1);
    setRebuildMessage(null);
  };

  const handleRebuildGraph = async () => {
    if (!selectedGraphPolicy?.domain) {
      return;
    }
    setIsRebuilding(true);
    setRebuildMessage(null);
    try {
      const result = await api.rebuildPolicyGraph(selectedGraphPolicy.domain);
      setGraphRefreshKey((current) => current + 1);
      setRebuildMessage(`Graph rebuilt: ${result.node_count} nodes in ${result.backend}.`);
    } catch (error) {
      setRebuildMessage(error instanceof Error ? error.message : "Rebuild failed");
    } finally {
      setIsRebuilding(false);
    }
  };

  const handleTabSelect = (tabId: PolicyTabId) => {
    setActiveTab(tabId);
  };

  const isStoreTab = activeTab === POLICY_TAB_STORE;
  const graphDomain = selectedGraphPolicy?.domain ?? "procurement";

  return (
    <div data-testid="policies-view" className="mx-auto flex max-w-7xl flex-col gap-6">
      <section className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Policy &amp; Governance</p>
        <h2 className="mt-2 text-2xl font-semibold">Policy store and knowledge graph</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
          {isStoreTab
            ? "Select a policy in the store to preview its knowledge graph. Use Ingest to add new policy documents."
            : "Add a new policy version to the store. After ingestion you will return to Policy Store to review it."}
        </p>
      </section>

      <section className="glass-card overflow-hidden rounded-2xl border border-[#e8e4df] bg-white shadow-sm">
        <div
          role="tablist"
          aria-label="Policy management"
          className="flex border-b border-[#e8e4df] bg-[#FAF9F7] px-2 pt-2"
        >
          {POLICY_TABS.map((tab) => {
            const isSelected = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                id={`policies-tab-${tab.id}`}
                data-testid={tab.testId}
                aria-selected={isSelected}
                aria-controls={`policies-panel-${tab.id}`}
                onClick={() => handleTabSelect(tab.id)}
                className={`rounded-t-xl px-5 py-3 text-sm font-medium transition ${
                  isSelected
                    ? "border border-b-white border-[#e8e4df] bg-white text-purple-700 shadow-sm"
                    : "text-slate-600 hover:bg-white/60 hover:text-slate-900"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="p-2 sm:p-4">
          <div
            role="tabpanel"
            id={`policies-panel-${POLICY_TAB_STORE}`}
            aria-labelledby={`policies-tab-${POLICY_TAB_STORE}`}
            hidden={!isStoreTab}
            data-testid="policies-panel-store"
          >
            {isStoreTab ? (
              <PolicyStorePanel
                embedded
                refreshKey={storeRefreshKey}
                onPolicyActivated={handlePolicyActivated}
                onPolicySelected={handlePolicySelected}
              />
            ) : null}
          </div>

          <div
            role="tabpanel"
            id={`policies-panel-${POLICY_TAB_INGEST}`}
            aria-labelledby={`policies-tab-${POLICY_TAB_INGEST}`}
            hidden={isStoreTab}
            data-testid="policies-panel-ingest"
          >
            {!isStoreTab ? <PolicyPanel embedded onPolicyIngested={handlePolicyIngested} /> : null}
          </div>
        </div>
      </section>

      {isStoreTab && selectedGraphPolicy ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-600">
              Knowledge graph for <span className="font-medium text-slate-900">{selectedGraphPolicy.title}</span>
            </p>
            <button
              type="button"
              data-testid="rebuild-policy-graph-button"
              disabled={isRebuilding}
              onClick={handleRebuildGraph}
              className="rounded-xl border border-purple-200 bg-purple-50 px-4 py-2 text-sm font-medium text-purple-700 disabled:opacity-50"
            >
              {isRebuilding ? "Rebuilding…" : "Rebuild Graph"}
            </button>
          </div>
          {rebuildMessage ? (
            <p className="-mt-3 text-sm text-slate-600" data-testid="rebuild-policy-graph-message">
              {rebuildMessage}
            </p>
          ) : null}
          <PolicyGraphPanel
            domain={graphDomain}
            policyId={selectedGraphPolicy.id}
            refreshKey={graphRefreshKey}
          />
        </>
      ) : null}
    </div>
  );
}

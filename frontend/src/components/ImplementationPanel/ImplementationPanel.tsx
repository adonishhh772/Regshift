"use client";

import { useRegShiftStore } from "@/lib/store";
import type { CodePatchRecord } from "@/lib/types";

interface ImplementationPanelProps {
  onApplyImplementation: () => void;
  onOpenChangePack: () => void;
}

function formatPatchObligation(obligation: string): string {
  return obligation.replace(/_/g, " ");
}

export function ImplementationPanel({
  onApplyImplementation,
  onOpenChangePack,
}: ImplementationPanelProps) {
  const packFilename = useRegShiftStore((state) => state.packFilename);
  const packMarkdown = useRegShiftStore((state) => state.packMarkdown);
  const implementationApplied = useRegShiftStore((state) => state.implementationApplied);
  const implementationPatches = useRegShiftStore((state) => state.implementationPatches);
  const repoPath = useRegShiftStore((state) => state.implementationRepoPath);
  const isLoading = useRegShiftStore((state) => state.isLoading);

  const canApply = Boolean(packMarkdown) && !isLoading;

  return (
    <section
      data-testid="implementation-panel"
      className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">ERPNext Implementation</p>
          <p className="mt-1 text-sm text-slate-600">
            Apply the approved change pack to ERPNext and extend the knowledge graph with code-change nodes.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            data-testid="open-change-pack-button"
            disabled={!packMarkdown}
            onClick={onOpenChangePack}
            className="rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium shadow-sm disabled:opacity-50"
          >
            Open Change Pack
          </button>
          <button
            type="button"
            data-testid="apply-erpnext-button"
            disabled={!canApply}
            onClick={onApplyImplementation}
            className="rounded-xl bg-gradient-to-r from-teal-500 to-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:opacity-50"
          >
            {implementationApplied ? "Re-apply to ERPNext" : "Apply to ERPNext"}
          </button>
        </div>
      </div>

      {packFilename ? (
        <p data-testid="implementation-pack-ref" className="mb-3 text-xs text-slate-500">
          Artifact: <span className="font-mono text-slate-700">{packFilename}</span>
        </p>
      ) : null}

      {implementationApplied ? (
        <div
          data-testid="implementation-success"
          className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
        >
          Patches applied. Knowledge graph extended with ImplementationPlan and CodeChange nodes linked to impacted
          files and obligations.
          {repoPath ? (
            <p className="mt-1 font-mono text-xs text-emerald-700">{repoPath}</p>
          ) : null}
        </div>
      ) : null}

      {implementationPatches.length > 0 ? (
        <ul data-testid="implementation-patch-list" className="space-y-2">
          {implementationPatches.map((patch: CodePatchRecord) => (
            <li
              key={patch.patch_id}
              className="rounded-xl border border-[#e8e4df] bg-[#FAF9F7] px-4 py-3 text-sm"
            >
              <p className="font-medium">{patch.description}</p>
              <p className="mt-1 font-mono text-xs text-slate-600">{patch.file_path}</p>
              <p className="mt-1 text-xs text-slate-500">
                {formatPatchObligation(patch.obligation)} · +{patch.lines_added} lines · {patch.change_type}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">
          Generate a change pack first, then apply contract obligations as RegShift-marked patches in the ERPNext
          workspace under <span className="font-mono">data/repos/erpnext</span>.
        </p>
      )}
    </section>
  );
}

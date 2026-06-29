"use client";

import { useRegShiftStore } from "@/lib/store";

interface ContractEditorProps {
  onCompile: () => void;
  onApprove: () => void;
}

export function ContractEditor({ onCompile, onApprove }: ContractEditorProps) {
  const contractYaml = useRegShiftStore((state) => state.contractYaml);
  const setContractYaml = useRegShiftStore((state) => state.setContractYaml);
  const contractApproved = useRegShiftStore((state) => state.contractApproved);
  const isLoading = useRegShiftStore((state) => state.isLoading);

  return (
    <section data-testid="contract-editor" className="glass-card rounded-2xl border border-[#e8e4df] bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Change Contract</p>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            contractApproved ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
          }`}
        >
          {contractApproved ? "Approved" : "Awaiting approval"}
        </span>
      </div>
      <textarea
        data-testid="contract-yaml"
        value={contractYaml}
        onChange={(event) => setContractYaml(event.target.value)}
        rows={16}
        className="w-full rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4 font-mono text-xs outline-none"
      />
      <div className="mt-4 flex gap-3">
        <button
          type="button"
          data-testid="compile-contract-button"
          disabled={isLoading}
          onClick={onCompile}
          className="rounded-xl border border-[#e8e4df] bg-white px-4 py-2 text-sm font-medium shadow-sm disabled:opacity-50"
        >
          Compile Change Contract
        </button>
        <button
          type="button"
          data-testid="approve-contract-button"
          disabled={isLoading || !contractYaml || contractApproved}
          onClick={onApprove}
          className="rounded-xl bg-gradient-to-r from-orange-500 to-red-500 px-4 py-2 text-sm font-medium text-white shadow-sm disabled:opacity-50"
        >
          Approve Contract
        </button>
      </div>
    </section>
  );
}

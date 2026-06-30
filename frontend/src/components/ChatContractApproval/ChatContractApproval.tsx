"use client";

import { type ChangeEvent } from "react";
import { CheckCircle2, ShieldCheck } from "lucide-react";

import type { ChatContractApprovalBlock } from "@/lib/types";

interface ChatContractApprovalProps {
  messageId: string;
  content: string;
  approval: ChatContractApprovalBlock;
  isLoading: boolean;
  onContractYamlChange: (messageId: string, contractYaml: string) => void;
  onApprove: (messageId: string) => void;
}

export function ChatContractApproval({
  messageId,
  content,
  approval,
  isLoading,
  onContractYamlChange,
  onApprove,
}: ChatContractApprovalProps) {
  const handleContractChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    onContractYamlChange(messageId, event.target.value);
  };

  const handleApproveClick = () => {
    onApprove(messageId);
  };

  return (
    <div
      data-testid="chat-contract-approval"
      className="w-full max-w-2xl overflow-hidden rounded-2xl border border-amber-200 bg-white shadow-sm"
    >
      <div className="border-b border-amber-200 bg-gradient-to-r from-amber-50 to-orange-50 px-4 py-3">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-amber-700">
            {approval.approved ? <CheckCircle2 size={18} /> : <ShieldCheck size={18} />}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-amber-800">
              {approval.approved ? "Contract approved" : "Human approval required"}
            </p>
            <p className="mt-1 text-sm leading-6 text-slate-700">{content}</p>
            {approval.domain ? (
              <p className="mt-1 text-xs text-slate-500">Domain: {approval.domain}</p>
            ) : null}
          </div>
        </div>
      </div>

      <div className="px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Change contract</p>
        <textarea
          data-testid="chat-contract-yaml"
          value={approval.contractYaml}
          onChange={handleContractChange}
          readOnly={approval.approved}
          rows={14}
          className="mt-2 w-full resize-y rounded-xl border border-[#e8e4df] bg-[#FAF9F7] p-4 font-mono text-xs leading-5 text-slate-700 outline-none ring-orange-500/10 focus:ring-2 disabled:cursor-default disabled:opacity-90"
        />
      </div>

      {!approval.approved ? (
        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-[#e8e4df] bg-[#FAF9F7] px-4 py-3">
          <p className="mr-auto text-xs text-slate-500">Edit the contract if needed, then approve to continue.</p>
          <button
            type="button"
            data-testid="chat-approve-contract-button"
            disabled={isLoading || !approval.contractYaml.trim()}
            onClick={handleApproveClick}
            className="rounded-xl bg-gradient-to-r from-orange-500 to-red-500 px-5 py-2.5 text-sm font-medium text-white shadow-sm disabled:opacity-50"
          >
            Approve contract &amp; continue
          </button>
        </div>
      ) : null}
    </div>
  );
}

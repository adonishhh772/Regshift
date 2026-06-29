"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";

const TYPE_BADGE: Record<string, string> = {
  BusinessChange: "BC",
  ChangeContract: "CC",
  Obligation: "OB",
  BusinessProcess: "BP",
  ERPModule: "MOD",
  File: "FILE",
  Symbol: "SYM",
  Risk: "RISK",
  Test: "TEST",
  ApprovalRole: "APR",
  EvidenceSnippet: "EVD",
};

function GraphNodeComponent({ data, selected }: NodeProps) {
  const nodeType = String(data.type ?? "");
  const badge = TYPE_BADGE[nodeType] ?? "N";

  return (
    <div
      className={`min-w-[140px] max-w-[180px] rounded-xl border bg-white px-3 py-2 shadow-sm ${
        selected ? "border-orange-400 ring-2 ring-orange-200" : "border-[#e8e4df]"
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-400" />
      <div className="flex items-start gap-2">
        <span className="rounded-md bg-slate-900 px-1.5 py-0.5 text-[9px] font-bold tracking-wider text-white">
          {badge}
        </span>
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-[#1a1a1a]">{String(data.label ?? "")}</p>
          <p className="mt-0.5 text-[9px] uppercase tracking-wider text-slate-500">{nodeType}</p>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-slate-400" />
    </div>
  );
}

export const GraphFlowNode = memo(GraphNodeComponent);

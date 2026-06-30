"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";

const TYPE_COLORS: Record<string, { ring: string; glow: string; badge: string }> = {
  PolicyDocument: { ring: "#f97316", glow: "rgba(249,115,22,0.45)", badge: "POL" },
  PolicyRule: { ring: "#6366f1", glow: "rgba(99,102,241,0.4)", badge: "RUL" },
  Obligation: { ring: "#ec4899", glow: "rgba(236,72,153,0.4)", badge: "OBL" },
  Threshold: { ring: "#14b8a6", glow: "rgba(20,184,166,0.4)", badge: "THR" },
  ApprovalRole: { ring: "#eab308", glow: "rgba(234,179,8,0.4)", badge: "ROL" },
  AgentLimit: { ring: "#8b5cf6", glow: "rgba(139,92,246,0.4)", badge: "LIM" },
  System: { ring: "#f97316", glow: "rgba(249,115,22,0.45)", badge: "SYS" },
  Package: { ring: "#6366f1", glow: "rgba(99,102,241,0.4)", badge: "PKG" },
  CodeFile: { ring: "#94a3b8", glow: "rgba(148,163,184,0.35)", badge: "FIL" },
  Artifact: { ring: "#14b8a6", glow: "rgba(20,184,166,0.4)", badge: "ART" },
  Symbol: { ring: "#10b981", glow: "rgba(16,185,129,0.4)", badge: "SYM" },
};

function shortenLabel(label: string, maxLength: number): string {
  if (label.length <= maxLength) {
    return label;
  }
  return `${label.slice(0, maxLength - 1)}…`;
}

function PolicyGraphNodeComponent({ data, selected }: NodeProps) {
  const nodeType = String(data.type ?? "");
  const colors = TYPE_COLORS[nodeType] ?? { ring: "#94a3b8", glow: "rgba(148,163,184,0.35)", badge: "N" };
  const label = String(data.label ?? "");

  return (
    <div
      title={label}
      className="flex w-[72px] flex-col items-center"
      data-testid={`policy-graph-node-${nodeType.toLowerCase()}`}
    >
      <Handle type="target" position={Position.Top} className="!h-1.5 !w-1.5 !border-0 !bg-transparent" />
      <div
        className={`flex h-11 w-11 items-center justify-center rounded-full border-2 bg-[#111827] text-[8px] font-bold tracking-wider text-white transition ${
          selected ? "scale-110" : ""
        }`}
        style={{
          borderColor: colors.ring,
          boxShadow: selected ? `0 0 18px ${colors.glow}` : `0 0 10px ${colors.glow}`,
        }}
      >
        {colors.badge}
      </div>
      <p className="mt-1 w-[88px] text-center text-[9px] leading-tight text-slate-300">
        {shortenLabel(label, 28)}
      </p>
      <Handle type="source" position={Position.Bottom} className="!h-1.5 !w-1.5 !border-0 !bg-transparent" />
    </div>
  );
}

export const PolicyGraphNode = memo(PolicyGraphNodeComponent);

import type { PolicyRule } from "@/lib/types";

interface PolicyRulesListProps {
  rules: PolicyRule[];
  maxHeightClassName?: string;
}

export function PolicyRulesList({ rules, maxHeightClassName = "max-h-[420px]" }: PolicyRulesListProps) {
  if (rules.length === 0) {
    return (
      <div
        data-testid="policy-rules-empty"
        className="rounded-xl border border-dashed border-[#e8e4df] bg-white px-4 py-6 text-center text-sm text-slate-500"
      >
        No extracted rules stored for this policy version.
      </div>
    );
  }

  return (
    <div data-testid="policy-rules-list" className={`space-y-2 overflow-y-auto ${maxHeightClassName}`}>
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

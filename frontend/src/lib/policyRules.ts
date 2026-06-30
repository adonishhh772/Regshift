import type { PolicyDocument, PolicyRule } from "@/lib/types";

export function getPolicyRules(policy: PolicyDocument): PolicyRule[] {
  const storedRules = policy.rules.rules;
  if (!Array.isArray(storedRules)) {
    return [];
  }
  return storedRules.filter(
    (rule): rule is PolicyRule =>
      typeof rule === "object" &&
      rule !== null &&
      typeof (rule as PolicyRule).id === "string" &&
      typeof (rule as PolicyRule).description === "string"
  );
}

export function getPolicyRuleCount(policy: PolicyDocument): number {
  if (typeof policy.rules.rule_count === "number") {
    return policy.rules.rule_count;
  }
  return getPolicyRules(policy).length;
}

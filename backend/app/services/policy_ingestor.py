import re
from typing import Any

from app.services.llm.constants import CONFIDENCE_DETERMINISTIC, CONFIDENCE_LLM, LlmTaskName
from app.services.llm.gateway import invoke_structured_task
from app.services.llm.prompts import POLICY_INGEST_SYSTEM_PROMPT, build_policy_ingest_user_prompt
from app.services.llm.schemas import LlmPolicyExtraction
from app.services.policy_constants import (
    DEFAULT_AGENT_LIMITS,
    OBLIGATION_PATTERNS,
    RULE_TYPE_AGENT_LIMIT,
    RULE_TYPE_APPROVAL_ROLE,
    RULE_TYPE_OBLIGATION,
    RULE_TYPE_THRESHOLD,
    SECTION_CITATION_PATTERN,
    WORD_NUMBERS,
)


def ingest_policy_document(
    title: str,
    source_text: str,
    domain: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    deterministic = _ingest_deterministic(title, source_text, domain)
    llm_extraction, meta = invoke_structured_task(
        LlmTaskName.POLICY_INGEST,
        LlmPolicyExtraction,
        POLICY_INGEST_SYSTEM_PROMPT,
        build_policy_ingest_user_prompt(title, source_text, domain),
        session_id=session_id,
    )

    if llm_extraction is None:
        deterministic["extraction_source"] = CONFIDENCE_DETERMINISTIC
        if meta is not None and meta.used_fallback_rules:
            deterministic["llm_fallback"] = True
        return deterministic

    merged = _merge_llm_policy(deterministic, llm_extraction, title)
    merged["extraction_source"] = CONFIDENCE_LLM
    if meta is not None:
        merged["llm_meta"] = meta.model_dump()
    if llm_extraction.reasoning:
        merged["reasoning"] = llm_extraction.reasoning
    return merged


def _ingest_deterministic(
    title: str,
    source_text: str,
    domain: str | None = None,
) -> dict[str, Any]:
    normalized = source_text.lower()
    sections = _split_into_sections(source_text)
    obligations = _extract_obligations(normalized, sections)
    threshold = _extract_threshold(normalized, domain)
    approval_roles = _extract_approval_roles(source_text)
    agent_limits = _extract_agent_limits(normalized)

    rules: list[dict[str, Any]] = []
    for obligation in obligations:
        rules.append(
            {
                "id": f"rule_{obligation['value']}",
                "type": RULE_TYPE_OBLIGATION,
                "value": obligation["value"],
                "citation": obligation["citation"],
                "description": obligation["description"],
            }
        )

    if threshold is not None:
        rules.append(
            {
                "id": "rule_threshold",
                "type": RULE_TYPE_THRESHOLD,
                "value": threshold,
                "citation": _find_threshold_citation(sections, normalized),
                "description": f"Approval threshold above {threshold}",
            }
        )

    for role in approval_roles:
        rules.append(
            {
                "id": f"rule_role_{role.lower().replace(' ', '_')}",
                "type": RULE_TYPE_APPROVAL_ROLE,
                "value": role,
                "citation": _find_role_citation(source_text, role),
                "description": f"Required approver: {role}",
            }
        )

    for limit_key, limit_value in agent_limits.items():
        rules.append(
            {
                "id": f"rule_limit_{limit_key}",
                "type": RULE_TYPE_AGENT_LIMIT,
                "key": limit_key,
                "value": limit_value,
                "citation": _find_agent_limit_citation(sections, normalized),
                "description": f"Agent limit: {limit_key}={limit_value}",
            }
        )

    inferred_domain = domain or _infer_domain(normalized, obligations)

    return {
        "title": title,
        "domain": inferred_domain,
        "obligations": [item["value"] for item in obligations],
        "threshold": threshold,
        "approval_roles": approval_roles,
        "agent_limits": agent_limits,
        "rules": rules,
        "rule_count": len(rules),
    }


def _merge_llm_policy(
    deterministic: dict[str, Any],
    extraction: LlmPolicyExtraction,
    title: str,
) -> dict[str, Any]:
    merged_rules = list(deterministic.get("rules", []))
    seen_rule_ids = {rule["id"] for rule in merged_rules}

    for llm_rule in extraction.rules:
        rule_dict = llm_rule.model_dump()
        if rule_dict["id"] in seen_rule_ids:
            continue
        merged_rules.append(rule_dict)
        seen_rule_ids.add(rule_dict["id"])

    obligations = list(
        dict.fromkeys(extraction.obligations + deterministic.get("obligations", []))
    )
    approval_roles = list(
        dict.fromkeys(extraction.approval_roles + deterministic.get("approval_roles", []))
    )
    agent_limits = dict(DEFAULT_AGENT_LIMITS)
    agent_limits.update(deterministic.get("agent_limits", {}))
    agent_limits.update(extraction.agent_limits)

    threshold = extraction.threshold if extraction.threshold is not None else deterministic.get("threshold")
    domain = extraction.domain or deterministic.get("domain", "procurement")

    return {
        "title": title,
        "domain": domain,
        "obligations": obligations,
        "threshold": threshold,
        "approval_roles": approval_roles,
        "agent_limits": agent_limits,
        "rules": merged_rules,
        "rule_count": len(merged_rules),
    }


def _split_into_sections(source_text: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current_citation = "document"
    current_lines: list[str] = []

    for line in source_text.splitlines():
        match = re.search(SECTION_CITATION_PATTERN, line, re.IGNORECASE)
        if match:
            if current_lines:
                sections.append({"citation": current_citation, "text": "\n".join(current_lines)})
            current_citation = match.group(1)
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append({"citation": current_citation, "text": "\n".join(current_lines)})
    return sections


def _extract_obligations(
    normalized: str,
    sections: list[dict[str, str]],
) -> list[dict[str, str]]:
    obligations: list[dict[str, str]] = []
    seen: set[str] = set()

    for pattern, obligation_value, description in OBLIGATION_PATTERNS:
        if not re.search(pattern, normalized):
            continue
        if obligation_value in seen:
            continue
        seen.add(obligation_value)
        citation = _find_obligation_citation(sections, pattern)
        obligations.append(
            {
                "value": obligation_value,
                "citation": citation,
                "description": description,
            }
        )
    return obligations


def _extract_threshold(normalized: str, domain: str | None) -> int | None:
    for phrase, value in WORD_NUMBERS.items():
        if phrase in normalized:
            return value

    amounts: list[int] = []
    for match in re.finditer(r"(?:£|gbp\s*)?\s*([\d][\d,]*)\s*k?\b", normalized):
        raw = match.group(1).replace(",", "")
        if not raw:
            continue
        value = int(raw)
        snippet_end = min(len(normalized), match.end() + 2)
        if "k" in normalized[match.end() : snippet_end]:
            value *= 1000
        amounts.append(value)

    if amounts:
        return max(amounts)

    default_thresholds: dict[str, int] = {
        "procurement": 25000,
        "inventory": 10000,
        "finance_billing": 0,
        "hr_compliance": 48,
        "security": 0,
    }
    if domain and domain in default_thresholds and default_thresholds[domain] > 0:
        return default_thresholds[domain]
    return None


def _extract_approval_roles(source_text: str) -> list[str]:
    roles: list[str] = []
    role_section = False
    for line in source_text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if "sign-off" in lower or "approval role" in lower or "required approver" in lower:
            role_section = True
            continue
        if role_section and stripped.startswith("-"):
            role = stripped.lstrip("- ").strip()
            if role:
                roles.append(role)
            continue
        if role_section and stripped and not stripped.startswith("-"):
            role_section = False

    role_patterns = [
        r"finance manager",
        r"procurement (?:owner|director|manager)",
        r"compliance reviewer",
        r"cfo",
        r"warehouse manager",
        r"engineering reviewer",
        r"administrator",
    ]
    normalized = source_text.lower()
    for pattern in role_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            role_label = match.group(0).title()
            if role_label not in roles:
                roles.append(role_label)

    return list(dict.fromkeys(roles))


def _extract_agent_limits(normalized: str) -> dict[str, bool]:
    limits = dict(DEFAULT_AGENT_LIMITS)
    if re.search(r"no autonomous|must not auto|auto.?merge.*(?:not|forbidden|blocked)", normalized):
        limits["can_auto_merge"] = False
    if re.search(r"human approval|requires human|human.?in.?the.?loop", normalized):
        limits["requires_human_approval"] = True
    if re.search(r"may generate tests|can generate tests", normalized):
        limits["can_generate_tests"] = True
    if re.search(r"may generate patch|can generate patch|propose changes", normalized):
        limits["can_generate_patch"] = True
    return limits


def _infer_domain(normalized: str, obligations: list[dict[str, str]]) -> str:
    domain_keywords: dict[str, list[str]] = {
        "procurement": ["purchase order", "supplier", "procurement", "buying"],
        "inventory": ["stock transfer", "warehouse", "dispatch", "inventory"],
        "finance_billing": ["invoice", "billing", "recurring", "refund", "cancellation fee"],
        "hr_compliance": ["employee", "hours", "compliance warning", "overtime"],
        "security": ["role change", "permission", "administrator", "access"],
    }
    scores: dict[str, int] = {domain: 0 for domain in domain_keywords}
    for domain, keywords in domain_keywords.items():
        for keyword in keywords:
            if keyword in normalized:
                scores[domain] += 1

    obligation_values = {item["value"] for item in obligations}
    if "warehouse_manager_approval_required" in obligation_values:
        scores["inventory"] += 2
    if "billing_transparency_required" in obligation_values:
        scores["finance_billing"] += 2
    if "permission_change_review_required" in obligation_values:
        scores["security"] += 2

    best_domain = max(scores, key=lambda key: scores[key])
    if scores[best_domain] == 0:
        return "procurement"
    return best_domain


def _find_obligation_citation(sections: list[dict[str, str]], pattern: str) -> str:
    for section in sections:
        if re.search(pattern, section["text"].lower()):
            return f"Section {section['citation']}"
    return "Policy document"


def _find_threshold_citation(sections: list[dict[str, str]], normalized: str) -> str:
    for section in sections:
        section_lower = section["text"].lower()
        if re.search(r"(?:£|gbp|exceed|above|threshold|amount)", section_lower):
            return f"Section {section['citation']}"
    return "Policy document"


def _find_role_citation(source_text: str, role: str) -> str:
    for section in _split_into_sections(source_text):
        if role.lower() in section["text"].lower():
            return f"Section {section['citation']}"
    return "Policy document"


def _find_agent_limit_citation(sections: list[dict[str, str]], normalized: str) -> str:
    for section in sections:
        section_lower = section["text"].lower()
        if re.search(r"autonomous|auto.?merge|human approval|agent", section_lower):
            return f"Section {section['citation']}"
    return "Policy document"

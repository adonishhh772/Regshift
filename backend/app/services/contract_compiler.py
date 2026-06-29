import re
from typing import Any

import yaml

from app.services.domain_loader import load_domain_pack
from app.services.policy_compiler import merge_policy_into_contract
from app.services.policy_constants import OBLIGATION_PATTERNS, WORD_NUMBERS


def compile_contract(text: str, domain: str, tenant_id: str | None = None) -> dict[str, Any]:
    pack = load_domain_pack(domain)
    normalized = text.lower()
    threshold = _extract_threshold(normalized, domain)
    entity = _extract_entity(pack, normalized)
    obligations = _extract_obligations(normalized, pack)
    exceptions = _build_exceptions(threshold, entity, domain)
    approval_roles = pack.get("approval_roles", [])
    risks = _build_risks(obligations, pack)
    required_tests = _build_tests(pack, entity, threshold)

    contract: dict[str, Any] = {
        "domain": domain,
        "entity": entity,
        "trigger": {"condition": f"total_amount > {threshold}"} if threshold else {},
        "required_behaviour": obligations,
        "exceptions": exceptions,
        "approval_roles": approval_roles,
        "risks": risks,
        "required_tests": required_tests,
    }

    contract = merge_policy_into_contract(contract, domain, tenant_id)
    policy_sourced = "policy_source" in contract

    contract_yaml = yaml.dump(contract, sort_keys=False, default_flow_style=False)
    return {
        "contract": contract,
        "contract_yaml": contract_yaml,
        "confidence": "policy_sourced" if policy_sourced else "deterministic",
    }


def parse_contract_yaml(contract_yaml: str) -> dict[str, Any]:
    return yaml.safe_load(contract_yaml)


def _extract_threshold(normalized: str, domain: str) -> int:
    default_thresholds: dict[str, int] = {
        "procurement": 25000,
        "inventory": 10000,
        "finance_billing": 0,
        "hr_compliance": 48,
        "security": 0,
    }
    for phrase, value in WORD_NUMBERS.items():
        if phrase in normalized:
            return value

    amounts: list[int] = []
    for match in re.finditer(r"(?:£|gbp\s*)?\s*([\d][\d,]*)\s*k?\b", normalized):
        raw = match.group(1).replace(",", "")
        if not raw:
            continue
        value = int(raw)
        if "k" in normalized[match.end() : match.end() + 2]:
            value *= 1000
        amounts.append(value)

    if amounts:
        return max(amounts)
    return default_thresholds.get(domain, 25000)


def _extract_entity(pack: dict[str, Any], normalized: str) -> str:
    entities = pack.get("business_entities", [])
    for entity in entities:
        if entity.replace("_", " ") in normalized or entity in normalized:
            return entity
    return entities[0] if entities else "entity"


def _extract_obligations(normalized: str, pack: dict[str, Any]) -> list[str]:
    obligations: list[str] = []
    for pattern, obligation, _description in OBLIGATION_PATTERNS:
        if re.search(pattern, normalized):
            obligations.append(obligation)

    if not obligations:
        templates = pack.get("test_templates", [])
        if templates:
            obligations = [
                "finance_approval_required",
                "supplier_confirmation_blocked_until_approval",
                "approval_event_logged",
            ]
    return list(dict.fromkeys(obligations))


def _build_exceptions(threshold: int, entity: str, domain: str) -> list[str]:
    if domain == "hr_compliance":
        return [f"employees_at_or_below_{threshold}_hours_follow_existing_flow"]
    if threshold:
        return [f"{entity}s_under_or_equal_to_{threshold}_follow_existing_flow"]
    return [f"existing_{entity}_flow_unchanged"]


def _build_risks(obligations: list[str], pack: dict[str, Any]) -> dict[str, str]:
    risks = {
        "financial_control": "medium",
        "supplier_operations": "medium",
        "permissions": "medium",
        "audit": "medium",
        "regression": "medium",
    }
    if "finance_approval_required" in obligations:
        risks["financial_control"] = "high"
    if "supplier_confirmation_blocked_until_approval" in obligations:
        risks["supplier_operations"] = "medium"
    if "approval_event_logged" in obligations:
        risks["audit"] = "high"
    if any("approval" in item for item in obligations):
        risks["permissions"] = "high"

    for rule in pack.get("risk_rules", []):
        if "financial_control high" in rule and "finance" in " ".join(obligations):
            risks["financial_control"] = "high"
        if "permission high" in rule and "approval" in " ".join(obligations):
            risks["permissions"] = "high"
        if "audit high" in rule and "log" in " ".join(obligations):
            risks["audit"] = "high"
    return risks


def _build_tests(pack: dict[str, Any], entity: str, threshold: int) -> list[str]:
    templates = pack.get("test_templates", [])
    tests: list[str] = []
    for template in templates:
        tests.append(
            template.format(entity=entity.replace("_", " "), threshold=f"£{threshold:,}")
        )
    return tests

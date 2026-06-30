from typing import Any

CLASSIFY_SYSTEM_PROMPT = (
    "You classify enterprise business change requests into exactly one domain. "
    "Domains: procurement, inventory, finance_billing, hr_compliance, security. "
    "Return structured JSON only."
)

CONTRACT_COMPILE_SYSTEM_PROMPT = (
    "You extract a machine-checkable Change Contract from a business change request. "
    "Use snake_case obligation identifiers such as finance_approval_required, "
    "supplier_confirmation_blocked_until_approval, approval_event_logged. "
    "Entity names use snake_case business entities like purchase_order. "
    "Return structured JSON only."
)

POLICY_INGEST_SYSTEM_PROMPT = (
    "You extract governance rules from enterprise policy documents. "
    "Rule types: obligation, threshold, approval_role, agent_limit. "
    "For agent_limit rules set key (e.g. can_auto_merge) and boolean value. "
    "Citations must reference policy sections. Return structured JSON only."
)

TEST_GENERATION_SYSTEM_PROMPT = (
    "You generate pytest test cases from an approved Change Contract YAML. "
    "Each test must map to a specific contract obligation or required_test entry. "
    "Use snake_case test ids prefixed with test_. "
    "pytest_code must be valid Python with def test_*(): and meaningful assert statements. "
    "Assertions must reference contract thresholds, roles, and entity names from the YAML. "
    "Return structured JSON only."
)

VALID_DOMAINS = (
    "procurement",
    "inventory",
    "finance_billing",
    "hr_compliance",
    "security",
)


def build_classify_user_prompt(text: str, domain_hints: list[str]) -> str:
    hints = ", ".join(domain_hints) if domain_hints else ", ".join(VALID_DOMAINS)
    return (
        f"Classify this business change.\n"
        f"Allowed domains: {hints}\n\n"
        f"Change request:\n{text}"
    )


def build_contract_user_prompt(text: str, domain: str, pack_context: dict[str, Any]) -> str:
    entities = pack_context.get("business_entities", [])
    keywords = pack_context.get("keywords", [])[:12]
    return (
        f"Domain: {domain}\n"
        f"Known entities: {', '.join(entities)}\n"
        f"Domain keywords: {', '.join(keywords)}\n\n"
        f"Business change:\n{text}"
    )


def build_policy_ingest_user_prompt(title: str, source_text: str, domain: str | None) -> str:
    domain_line = f"Suggested domain: {domain}\n" if domain else ""
    return (
        f"Policy title: {title}\n"
        f"{domain_line}\n"
        f"Policy document:\n{source_text}"
    )


def build_test_generation_user_prompt(contract_yaml: str, domain: str, pack_context: dict[str, Any]) -> str:
    entities = pack_context.get("business_entities", [])
    keywords = pack_context.get("keywords", [])[:12]
    return (
        f"Domain: {domain}\n"
        f"Known entities: {', '.join(entities)}\n"
        f"Domain keywords: {', '.join(keywords)}\n\n"
        f"Approved Change Contract YAML:\n{contract_yaml}\n\n"
        f"Generate 6-10 pytest tests covering every required_behaviour obligation, "
        f"approval_roles permission checks, and required_tests scenarios."
    )

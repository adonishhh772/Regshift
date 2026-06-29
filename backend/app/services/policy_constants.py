from typing import Final

DEFAULT_TENANT_ID: Final[str] = "demo_org"

POLICY_STATUS_ACTIVE: Final[str] = "active"
POLICY_STATUS_ARCHIVED: Final[str] = "archived"

RULE_TYPE_OBLIGATION: Final[str] = "obligation"
RULE_TYPE_THRESHOLD: Final[str] = "threshold"
RULE_TYPE_APPROVAL_ROLE: Final[str] = "approval_role"
RULE_TYPE_AGENT_LIMIT: Final[str] = "agent_limit"

OBLIGATION_PATTERNS: list[tuple[str, str, str]] = [
    (r"finance\s+(?:manager\s+)?approv|finance\s+approv", "finance_approval_required", "Finance approval requirement"),
    (
        r"block.*confirm|confirm.*block|before\s+supplier|blocked until",
        "supplier_confirmation_blocked_until_approval",
        "Supplier confirmation blocked until approval",
    ),
    (r"log|audit|record", "approval_event_logged", "Approval event audit logging"),
    (
        r"compliance\s+warning|manager\s+review",
        "compliance_warning_and_manager_review",
        "Compliance warning and manager review",
    ),
    (
        r"recurring\s+charges|cancellation\s+fees|refund\s+terms",
        "billing_transparency_required",
        "Billing transparency disclosure",
    ),
    (
        r"role\s+change|financial\s+permission",
        "permission_change_review_required",
        "Permission change review",
    ),
    (
        r"warehouse\s+manager\s+approv",
        "warehouse_manager_approval_required",
        "Warehouse manager approval",
    ),
    (
        r"no autonomous|human approval|requires human",
        "human_approval_required",
        "Human approval required for changes",
    ),
]

SECTION_CITATION_PATTERN: Final[str] = r"(?:section|§|article|clause)\s+([\d]+(?:\.[\d]+)*)"

WORD_NUMBERS: dict[str, int] = {
    "twenty-five thousand": 25000,
    "twenty five thousand": 25000,
    "fifty thousand": 50000,
    "fifty thousand pounds": 50000,
    "ten thousand": 10000,
    "forty-eight": 48,
}

DEFAULT_AGENT_LIMITS: dict[str, bool] = {
    "can_generate_tests": True,
    "can_generate_patch": True,
    "can_auto_merge": False,
    "requires_human_approval": True,
}

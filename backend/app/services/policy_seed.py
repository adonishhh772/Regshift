from app.config import settings
from app.services.policy_graph import persist_policy_knowledge_graph
from app.services.policy_ingestor import ingest_policy_document
from app.services.policy_store import get_active_policy, ingest_policy

DEMO_INVENTORY_POLICY = """
ACME Corp Inventory Policy v1.0

Section 3.1 - Stock Adjustments
All stock adjustments exceeding 500 units require Warehouse Manager approval.

Section 3.2 - Cycle Count Controls
Cycle count variances above 2% must be logged and reviewed by Inventory Control.

Section 4.1 - Audit Requirements
Every inventory adjustment must record approver identity and timestamp.

Section 5.1 - Agent Automation Limits
No autonomous system changes to inventory approval workflows are permitted.
All changes require human approval before merge to production.

Section 6.1 - Required Sign-off Roles
- Warehouse Manager
- Inventory Control Lead
"""

DEMO_FINANCE_POLICY = """
ACME Corp Finance & Billing Policy v1.2

Section 2.1 - Invoice Approval
All invoices exceeding £50,000 must receive Finance Director approval.

Section 2.2 - Recurring Charges
Recurring charges, cancellation fees, and refund terms must be disclosed to customers.

Section 3.1 - Audit Requirements
Every billing approval event must be logged with approver identity and timestamp.

Section 4.1 - Agent Automation Limits
No autonomous system changes to billing approval workflows are permitted.
All changes require human approval before merge to production.

Section 5.1 - Required Sign-off Roles
- Finance Director
- Billing Operations Owner
- Compliance Reviewer
"""

DEMO_POLICY_SEEDS: list[dict[str, str]] = [
    {
        "domain": "procurement",
        "title": "ACME Corp Procurement Policy v2.1",
        "file_name": "demo_org_procurement_policy.txt",
    },
    {
        "domain": "inventory",
        "title": "ACME Corp Inventory Policy v1.0",
        "inline_text": DEMO_INVENTORY_POLICY,
    },
    {
        "domain": "finance_billing",
        "title": "ACME Corp Finance & Billing Policy v1.2",
        "inline_text": DEMO_FINANCE_POLICY,
    },
]


def _seed_policy(domain: str, title: str, source_text: str) -> dict[str, str] | None:
    if get_active_policy(domain):
        return None
    parsed = ingest_policy_document(
        title=title,
        source_text=source_text,
        domain=domain,
    )
    stored = ingest_policy(
        title=parsed["title"],
        source_text=source_text,
        rules=parsed,
        domain=parsed["domain"],
    )
    persist_policy_knowledge_graph(stored["tenant_id"], stored)
    return {"policy_id": stored["id"], "domain": stored["domain"]}


def seed_demo_policies() -> dict[str, str] | None:
    seeded: list[dict[str, str]] = []
    for seed in DEMO_POLICY_SEEDS:
        domain = seed["domain"]
        title = seed["title"]
        if "inline_text" in seed:
            result = _seed_policy(domain, title, seed["inline_text"])
        else:
            policy_path = settings.data_dir / "sample_policies" / seed["file_name"]
            if not policy_path.exists():
                continue
            result = _seed_policy(domain, title, policy_path.read_text(encoding="utf-8"))
        if result:
            seeded.append(result)
    if not seeded:
        return None
    return seeded[0]

from pathlib import Path

from app.config import settings
from app.services.policy_graph import persist_policy_knowledge_graph
from app.services.policy_ingestor import ingest_policy_document
from app.services.policy_store import get_active_policy, ingest_policy


def seed_demo_policies() -> dict[str, str] | None:
    if get_active_policy("procurement"):
        existing = get_active_policy("procurement")
        if existing:
            persist_policy_knowledge_graph(existing["tenant_id"], existing)
        return None

    policy_path = settings.data_dir / "sample_policies" / "demo_org_procurement_policy.txt"
    if not policy_path.exists():
        return None

    source_text = policy_path.read_text(encoding="utf-8")
    parsed = ingest_policy_document(
        title="ACME Corp Procurement Policy v2.1",
        source_text=source_text,
        domain="procurement",
    )
    stored = ingest_policy(
        title=parsed["title"],
        source_text=source_text,
        rules=parsed,
        domain=parsed["domain"],
    )
    persist_policy_knowledge_graph(stored["tenant_id"], stored)
    return {"policy_id": stored["id"], "domain": stored["domain"]}

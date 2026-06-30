import json
from typing import Any

from app.models.schemas import ImpactedFile
from app.services.domain_loader import load_domain_pack
from app.services.scanner import search_index
from app.services.system_graph_store import search_impacted_files
from app.services.system_identifier import resolve_target_system_ids


PROCESS_MAP: dict[str, list[str]] = {
    "procurement": [
        "PurchaseOrderCreation",
        "FinanceApprovalGate",
        "SupplierConfirmation",
    ],
    "inventory": [
        "StockTransferDispatch",
        "WarehouseManagerApproval",
    ],
    "finance_billing": [
        "InvoiceConfirmation",
        "BillingTransparencyReview",
    ],
    "hr_compliance": [
        "WorkingHoursComplianceCheck",
        "ManagerReviewWorkflow",
    ],
    "security": [
        "RoleChangeReview",
        "FinancialPermissionAudit",
    ],
}


def analyze_impact(
    contract: dict[str, Any],
    domain: str,
    session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pack = load_domain_pack(domain)
    keywords = list(pack.get("keywords", []))
    entity = contract.get("entity", "")
    if entity:
        keywords.extend([entity, entity.replace("_", " ")])

    target_system_ids = resolve_target_system_ids(session or {})
    raw_files: list[dict[str, Any]] = []
    impact_source = "keyword_index"

    if target_system_ids:
        raw_files = search_impacted_files(target_system_ids, keywords, limit=15)
        if raw_files:
            impact_source = "system_kg"

    if not raw_files:
        raw_files = search_index(keywords, limit=15)

    files: list[ImpactedFile] = []
    for raw in raw_files:
        symbols = json.loads(raw.get("python_functions", "[]") or "[]")[:5]
        matched = raw.get("matched_keywords", [])
        if isinstance(matched, str):
            matched = json.loads(matched)

        path = raw["path"]
        if raw.get("system_id"):
            path = f"{raw['system_id']}:{path}"

        files.append(
            ImpactedFile(
                path=path,
                module=raw.get("module", "unknown"),
                score=round(float(raw.get("score", 0)), 1),
                evidence_snippet=raw.get("content_snippet", "")[:240],
                keywords=matched if isinstance(matched, list) else [],
                symbols=symbols,
            )
        )

    modules = sorted({file.module for file in files})
    likely_modules = pack.get("likely_modules", [])
    for module in likely_modules:
        if module not in modules:
            modules.append(module)

    processes = PROCESS_MAP.get(domain, ["BusinessProcessReview"])

    return {
        "processes": processes,
        "modules": modules[:8],
        "files": files,
        "impact_source": impact_source,
        "target_systems": target_system_ids,
    }

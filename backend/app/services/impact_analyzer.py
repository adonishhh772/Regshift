import json
from typing import Any

from app.models.schemas import ImpactedFile
from app.services.domain_loader import load_domain_pack
from app.services.scanner import search_index


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


def analyze_impact(contract: dict[str, Any], domain: str) -> dict[str, Any]:
    pack = load_domain_pack(domain)
    keywords = pack.get("keywords", [])
    entity = contract.get("entity", "")
    if entity:
        keywords = keywords + [entity, entity.replace("_", " ")]

    raw_files = search_index(keywords, limit=15)
    files: list[ImpactedFile] = []

    for raw in raw_files:
        symbols = json.loads(raw.get("python_functions", "[]") or "[]")[:5]
        matched = raw.get("matched_keywords", [])
        if isinstance(matched, str):
            matched = json.loads(matched)

        files.append(
            ImpactedFile(
                path=raw["path"],
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
    }

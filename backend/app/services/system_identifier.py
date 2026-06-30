from typing import Any

from app.services.system_catalog import load_system_catalog
from app.services.system_constants import SYSTEM_ROLE_PRIMARY, SYSTEM_ROLE_RELATED
from app.services.system_graph_store import get_system_ingest_status


def identify_systems(text: str, domain: str | None = None) -> dict[str, Any]:
    normalized = text.lower()
    catalog = load_system_catalog()
    scored: list[tuple[float, dict[str, Any]]] = []

    for system in catalog:
        system_id = str(system.get("id"))
        score = 0.0
        matched_signals: list[str] = []

        system_domains = system.get("domains") or []
        if domain and domain in system_domains:
            score += 3.0
            matched_signals.append(f"domain:{domain}")

        for keyword in system.get("keywords") or []:
            keyword_lower = str(keyword).lower()
            if keyword_lower in normalized:
                score += 1.5 + len(keyword_lower) / 40.0
                matched_signals.append(keyword_lower)

        vendor = str(system.get("vendor", "")).lower()
        system_name = str(system.get("name", "")).lower()
        if vendor and vendor in normalized:
            score += 2.0
            matched_signals.append(vendor)
        if system_name and system_name in normalized:
            score += 2.5
            matched_signals.append(system_name)

        ingest_status = get_system_ingest_status(system_id)
        if ingest_status.get("status") == "ready":
            score += 0.5

        if score <= 0:
            continue

        scored.append(
            (
                score,
                {
                    "system_id": system_id,
                    "name": system.get("name", system_id),
                    "vendor": system.get("vendor", "unknown"),
                    "confidence": 0.0,
                    "matched_signals": matched_signals,
                    "ingested": ingest_status.get("status") == "ready",
                },
            )
        )

    if not scored:
        fallback = _fallback_by_domain(domain, catalog)
        if fallback:
            scored = [(2.0, fallback)]

    scored.sort(key=lambda item: item[0], reverse=True)
    total_score = sum(item[0] for item in scored) or 1.0

    systems: list[dict[str, Any]] = []
    for index, (score, payload) in enumerate(scored[:5]):
        confidence = round(min(score / total_score, 0.99), 2)
        role = SYSTEM_ROLE_PRIMARY if index == 0 else SYSTEM_ROLE_RELATED
        systems.append(
            {
                **payload,
                "confidence": confidence,
                "role": role,
            }
        )

    primary_system_id = systems[0]["system_id"] if systems else None
    needs_confirmation = len(systems) > 1 and systems[0]["confidence"] < 0.6

    return {
        "primary_system_id": primary_system_id,
        "systems": systems,
        "needs_confirmation": needs_confirmation,
        "confirmed": False,
    }


def resolve_target_system_ids(session: dict[str, Any]) -> list[str]:
    import json

    raw = session.get("target_systems_json")
    if not isinstance(raw, str) or not raw.strip():
        return []
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        return []
    if not payload.get("confirmed"):
        primary = payload.get("primary_system_id")
        return [primary] if primary else []
    systems = payload.get("systems") or []
    return [str(item["system_id"]) for item in systems if item.get("system_id")]


def _fallback_by_domain(domain: str | None, catalog: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not domain:
        return None
    for system in catalog:
        if domain in (system.get("domains") or []):
            system_id = str(system.get("id"))
            return {
                "system_id": system_id,
                "name": system.get("name", system_id),
                "vendor": system.get("vendor", "unknown"),
                "confidence": 0.0,
                "matched_signals": [f"domain_default:{domain}"],
                "ingested": get_system_ingest_status(system_id).get("status") == "ready",
            }
    return None

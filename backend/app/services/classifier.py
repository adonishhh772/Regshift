from typing import Any

from app.services.domain_loader import load_all_domain_packs


def classify_change(text: str, override_domain: str | None = None) -> dict[str, Any]:
    if override_domain:
        return {
            "domain": override_domain,
            "confidence": 1.0,
            "alternatives": [],
        }

    normalized = text.lower()
    packs = load_all_domain_packs()
    scores: dict[str, float] = {}

    for domain, pack in packs.items():
        score = 0.0
        keywords = pack.get("keywords", [])
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in normalized:
                score += 1.0 + (len(keyword_lower) / 20.0)
        scores[domain] = score

    if not scores or max(scores.values()) == 0:
        return {
            "domain": "procurement",
            "confidence": 0.3,
            "alternatives": [{"domain": name, "score": value} for name, value in scores.items()],
        }

    sorted_domains = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_domain, top_score = sorted_domains[0]
    total_score = sum(scores.values()) or 1.0
    confidence = min(top_score / total_score, 0.99)

    alternatives = [
        {"domain": domain, "score": round(score / total_score, 2)}
        for domain, score in sorted_domains[1:4]
        if score > 0
    ]

    return {
        "domain": top_domain,
        "confidence": round(confidence, 2),
        "alternatives": alternatives,
    }

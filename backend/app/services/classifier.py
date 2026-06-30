from typing import Any

from app.services.domain_loader import load_all_domain_packs
from app.services.llm.constants import CONFIDENCE_DETERMINISTIC, CONFIDENCE_LLM, LlmTaskName
from app.services.llm.gateway import invoke_structured_task
from app.services.llm.prompts import CLASSIFY_SYSTEM_PROMPT, build_classify_user_prompt
from app.services.llm.schemas import LlmClassifyResult


def classify_change(
    text: str,
    override_domain: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    if override_domain:
        return {
            "domain": override_domain,
            "confidence": 1.0,
            "alternatives": [],
            "source": CONFIDENCE_DETERMINISTIC,
        }

    deterministic = _classify_deterministic(text)
    llm_result, meta = invoke_structured_task(
        LlmTaskName.CLASSIFY,
        LlmClassifyResult,
        CLASSIFY_SYSTEM_PROMPT,
        build_classify_user_prompt(text, list(load_all_domain_packs().keys())),
        session_id=session_id,
    )

    if llm_result is None:
        deterministic["source"] = CONFIDENCE_DETERMINISTIC
        if meta is not None and meta.used_fallback_rules:
            deterministic["llm_fallback"] = True
        return deterministic

    merged = _merge_classify_results(deterministic, llm_result)
    merged["source"] = CONFIDENCE_LLM
    if meta is not None:
        merged["llm_meta"] = meta.model_dump()
    return merged


def _classify_deterministic(text: str) -> dict[str, Any]:
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


def _merge_classify_results(
    deterministic: dict[str, Any],
    llm_result: LlmClassifyResult,
) -> dict[str, Any]:
    packs = load_all_domain_packs()
    domain = llm_result.domain if llm_result.domain in packs else deterministic["domain"]
    confidence = round(llm_result.confidence, 2)
    alternatives = [
        {"domain": alt.domain, "score": round(alt.score, 2)}
        for alt in llm_result.alternatives
        if alt.domain in packs
    ]
    if not alternatives:
        alternatives = deterministic.get("alternatives", [])
    return {
        "domain": domain,
        "confidence": confidence,
        "alternatives": alternatives,
        "reasoning": llm_result.reasoning,
    }

import time
import threading
from typing import Any, TypeVar

from pydantic import BaseModel

from app.config import settings
from app.services.llm.constants import (
    LLM_ROUTE_CHAIN_SEPARATOR,
    LLM_ROUTE_SEPARATOR,
    LlmTaskName,
)
from app.services.llm.providers import provider_is_configured, structured_invoke
from app.services.llm.schemas import LlmGatewayStatus, LlmInvocationMeta, ModelRoute

SchemaT = TypeVar("SchemaT", bound=BaseModel)

_LLM_CONCURRENCY_LIMIT = 4
_LLM_SEMAPHORE = threading.BoundedSemaphore(_LLM_CONCURRENCY_LIMIT)
_LLM_ACQUIRE_TIMEOUT_SECONDS = 30.0


def parse_route_chain(raw_value: str) -> list[ModelRoute]:
    routes: list[ModelRoute] = []
    for segment in raw_value.split(LLM_ROUTE_CHAIN_SEPARATOR):
        trimmed = segment.strip()
        if not trimmed:
            continue
        if LLM_ROUTE_SEPARATOR not in trimmed:
            continue
        provider, model = trimmed.split(LLM_ROUTE_SEPARATOR, 1)
        provider_name = provider.strip()
        model_name = model.strip()
        if not provider_name or not model_name:
            continue
        routes.append(ModelRoute(provider=provider_name, model=model_name))
    return routes


def resolve_task_routes(task: LlmTaskName) -> list[ModelRoute]:
    route_map: dict[LlmTaskName, str] = {
        LlmTaskName.CLASSIFY: settings.llm_route_classify,
        LlmTaskName.CONTRACT_COMPILE: settings.llm_route_contract,
        LlmTaskName.POLICY_INGEST: settings.llm_route_policy_ingest,
        LlmTaskName.TEST_GENERATION: settings.llm_route_test_generation,
    }
    routes = parse_route_chain(route_map[task])
    configured_routes = [route for route in routes if provider_is_configured(route.provider)]
    return configured_routes


def gateway_status() -> dict[str, Any]:
    status = LlmGatewayStatus(
        enabled=settings.llm_gateway_enabled,
        fallback_to_rules=settings.llm_fallback_to_rules,
        routes={
            LlmTaskName.CLASSIFY: resolve_task_routes(LlmTaskName.CLASSIFY),
            LlmTaskName.CONTRACT_COMPILE: resolve_task_routes(LlmTaskName.CONTRACT_COMPILE),
            LlmTaskName.POLICY_INGEST: resolve_task_routes(LlmTaskName.POLICY_INGEST),
            LlmTaskName.TEST_GENERATION: resolve_task_routes(LlmTaskName.TEST_GENERATION),
        },
        providers_configured={
            "openai": provider_is_configured("openai"),
            "gateway": provider_is_configured("gateway"),
            "azure_openai": provider_is_configured("azure_openai"),
            "anthropic": provider_is_configured("anthropic"),
        },
        default_temperature=settings.llm_temperature,
        request_timeout_seconds=settings.llm_request_timeout_seconds,
    )
    return status.model_dump()


def invoke_structured_task(
    task: LlmTaskName,
    schema: type[SchemaT],
    system_prompt: str,
    user_prompt: str,
    session_id: str | None = None,
) -> tuple[SchemaT | None, LlmInvocationMeta | None]:
    if not settings.llm_gateway_enabled:
        return None, None

    routes = resolve_task_routes(task)
    if not routes:
        return None, None

    last_error: Exception | None = None
    acquired = _LLM_SEMAPHORE.acquire(timeout=_LLM_ACQUIRE_TIMEOUT_SECONDS)
    if not acquired:
        if settings.llm_fallback_to_rules:
            meta = LlmInvocationMeta(
                task=task,
                provider=routes[0].provider,
                model=routes[0].model,
                route_index=0,
                used_fallback_rules=True,
            )
            return None, meta
        raise TimeoutError("LLM concurrency limit reached; try again shortly")

    try:
        for index, route in enumerate(routes):
            started = time.perf_counter()
            try:
                with _trace_llm_step(task, route, session_id, index):
                    result = structured_invoke(
                        route.provider,
                        route.model,
                        schema,
                        system_prompt,
                        user_prompt,
                    )
                latency_ms = int((time.perf_counter() - started) * 1000)
                meta = LlmInvocationMeta(
                    task=task,
                    provider=route.provider,
                    model=route.model,
                    route_index=index,
                    latency_ms=latency_ms,
                    used_fallback_rules=False,
                )
                return result, meta
            except Exception as error:
                last_error = error
                continue
    finally:
        _LLM_SEMAPHORE.release()

    if last_error is not None and settings.llm_fallback_to_rules:
        meta = LlmInvocationMeta(
            task=task,
            provider=routes[0].provider,
            model=routes[0].model,
            route_index=0,
            used_fallback_rules=True,
        )
        return None, meta

    if last_error is not None:
        raise last_error
    return None, None


def _trace_llm_step(
    task: LlmTaskName,
    route: ModelRoute,
    session_id: str | None,
    route_index: int,
):
    from app.services.langfuse_tracer import trace_regshift_step

    return trace_regshift_step(
        f"llm-{task}",
        session_id or "llm-gateway",
        input_data={
            "provider": route.provider,
            "model": route.model,
            "route_index": route_index,
        },
        metadata={"task": task},
    )

import os

import pytest

from app.config import settings
from app.services.llm.constants import LlmTaskName
from app.services.llm.gateway import gateway_status, invoke_structured_task, parse_route_chain, resolve_task_routes
from app.services.llm.schemas import LlmClassifyResult


@pytest.fixture(autouse=True)
def llm_gateway_disabled():
    previous_enabled = settings.llm_gateway_enabled
    previous_fallback = settings.llm_fallback_to_rules
    previous_openai_key = settings.openai_api_key
    settings.llm_gateway_enabled = False
    settings.llm_fallback_to_rules = True
    settings.openai_api_key = None
    os.environ.pop("OPENAI_API_KEY", None)
    yield
    settings.llm_gateway_enabled = previous_enabled
    settings.llm_fallback_to_rules = previous_fallback
    settings.openai_api_key = previous_openai_key


def test_parse_route_chain_supports_fallbacks():
    routes = parse_route_chain("openai:gpt-4o-mini,azure_openai:deploy-mini,gateway:gpt-4o")
    assert len(routes) == 3
    assert routes[0].provider == "openai"
    assert routes[0].model == "gpt-4o-mini"
    assert routes[2].provider == "gateway"


def test_gateway_status_when_disabled():
    status = gateway_status()
    assert status["enabled"] is False
    assert status["fallback_to_rules"] is True
    assert LlmTaskName.CLASSIFY in status["routes"]


def test_invoke_returns_none_when_gateway_disabled():
    result, meta = invoke_structured_task(
        LlmTaskName.CLASSIFY,
        LlmClassifyResult,
        "system",
        "user",
        session_id="test-session",
    )
    assert result is None
    assert meta is None


def test_resolve_task_routes_filters_unconfigured_providers():
    settings.llm_gateway_enabled = True
    settings.llm_route_classify = "openai:gpt-4o-mini,azure_openai:missing"
    settings.openai_api_key = "test-key"
    settings.azure_openai_api_key = None
    settings.azure_openai_endpoint = None
    routes = resolve_task_routes(LlmTaskName.CLASSIFY)
    assert len(routes) == 1
    assert routes[0].provider == "openai"


def test_invoke_structured_task_uses_mocked_provider():
    settings.llm_gateway_enabled = True
    settings.llm_route_classify = "openai:gpt-4o-mini"
    settings.openai_api_key = "test-key"

    expected = LlmClassifyResult(
        domain="procurement",
        confidence=0.92,
        alternatives=[],
        reasoning="Purchase order controls",
    )

    from app.services.llm import gateway as gateway_module

    original_invoke = gateway_module.structured_invoke

    def mock_structured_invoke(provider, model, schema, system_prompt, user_prompt):
        assert provider == "openai"
        assert model == "gpt-4o-mini"
        return expected

    gateway_module.structured_invoke = mock_structured_invoke
    try:
        result, meta = invoke_structured_task(
            LlmTaskName.CLASSIFY,
            LlmClassifyResult,
            "system",
            "user",
            session_id="session-1",
        )
    finally:
        gateway_module.structured_invoke = original_invoke

    assert result is not None
    assert result.domain == "procurement"
    assert meta is not None
    assert meta.provider == "openai"
    assert meta.used_fallback_rules is False

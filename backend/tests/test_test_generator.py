import pytest

from app.config import settings
from app.services.llm.constants import LlmTaskName
from app.services.llm.schemas import LlmGeneratedTestItem, LlmTestGenerationResult
from app.services.test_generator import _generate_tests_deterministic, generate_tests
from app.services.simulator import (
    OBLIGATION_APPROVAL_LOGGED,
    OBLIGATION_FINANCE_APPROVAL,
    OBLIGATION_SUPPLIER_BLOCKED,
)


PROCUREMENT_CONTRACT = {
    "entity": "purchase_order",
    "trigger": {"condition": "total_amount > 25000"},
    "required_behaviour": [
        OBLIGATION_FINANCE_APPROVAL,
        OBLIGATION_SUPPLIER_BLOCKED,
        OBLIGATION_APPROVAL_LOGGED,
    ],
    "approval_roles": ["Finance Manager"],
}


@pytest.fixture
def llm_gateway_disabled():
    previous_enabled = settings.llm_gateway_enabled
    previous_fallback = settings.llm_fallback_to_rules
    previous_openai_key = settings.openai_api_key
    settings.llm_gateway_enabled = False
    settings.llm_fallback_to_rules = True
    settings.openai_api_key = None
    yield
    settings.llm_gateway_enabled = previous_enabled
    settings.llm_fallback_to_rules = previous_fallback
    settings.openai_api_key = previous_openai_key


def test_deterministic_tests_cover_contract_obligations():
    tests = _generate_tests_deterministic(PROCUREMENT_CONTRACT, "procurement")
    rules = {test.contract_rule for test in tests}

    assert OBLIGATION_FINANCE_APPROVAL in rules
    assert OBLIGATION_SUPPLIER_BLOCKED in rules
    assert OBLIGATION_APPROVAL_LOGGED in rules
    assert len(tests) >= 6


def test_deterministic_tests_reference_threshold(llm_gateway_disabled):
    tests = generate_tests(PROCUREMENT_CONTRACT, "procurement")
    combined = "\n".join(test.pytest_code for test in tests)

    assert "25000" in combined
    assert all(test.pytest_code.startswith("def test_") for test in tests)


def test_llm_test_generation_when_gateway_returns_results(monkeypatch):
    settings.llm_gateway_enabled = True
    settings.openai_api_key = "test-key"

    expected = LlmTestGenerationResult(
        tests=[
            LlmGeneratedTestItem(
                id="test_po_blocked_without_finance",
                name="PO blocked without finance approval",
                description="Purchase order above threshold without finance approval must be blocked",
                contract_rule=OBLIGATION_FINANCE_APPROVAL,
                assertions=["result == 'blocked'", "has_finance_approval is False"],
                pytest_code="def test_po_blocked_without_finance():\n    assert True\n",
            )
        ]
    )

    from app.services.llm.schemas import LlmInvocationMeta

    def mock_invoke(task, schema, system_prompt, user_prompt, session_id=None):
        assert task == LlmTaskName.TEST_GENERATION
        assert "purchase_order" in user_prompt

        return expected, LlmInvocationMeta(task=task, provider="openai", model="gpt-4o-mini")

    monkeypatch.setattr(
        "app.services.test_generator.invoke_structured_task",
        mock_invoke,
    )

    tests = generate_tests(PROCUREMENT_CONTRACT, "procurement", session_id="sess-1")

    assert len(tests) == 1
    assert tests[0].id == "test_po_blocked_without_finance"
    assert "Generated via LLM" in tests[0].pytest_code

    settings.llm_gateway_enabled = False
    settings.openai_api_key = None

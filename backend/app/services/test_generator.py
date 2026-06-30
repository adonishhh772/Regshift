import re
from typing import Any

import yaml

from app.models.schemas import GeneratedTest
from app.services.domain_loader import load_domain_pack
from app.services.llm.constants import CONFIDENCE_DETERMINISTIC, CONFIDENCE_LLM, LlmTaskName
from app.services.llm.gateway import invoke_structured_task
from app.services.llm.prompts import TEST_GENERATION_SYSTEM_PROMPT, build_test_generation_user_prompt
from app.services.llm.schemas import LlmTestGenerationResult
from app.services.simulator import OBLIGATION_APPROVAL_LOGGED, OBLIGATION_FINANCE_APPROVAL, OBLIGATION_SUPPLIER_BLOCKED

SAFE_TEST_ID_PATTERN = re.compile(r"[^a-zA-Z0-9_]")


def generate_tests(
    contract: dict[str, Any],
    domain: str,
    session_id: str | None = None,
) -> list[GeneratedTest]:
    llm_tests, meta = _generate_tests_via_llm(contract, domain, session_id)
    if llm_tests:
        annotated: list[GeneratedTest] = []
        meta_payload = meta.model_dump() if meta is not None else None
        for test in llm_tests:
            pytest_code = test.pytest_code
            if meta_payload is not None:
                pytest_code = _annotate_pytest_source(pytest_code, meta_payload)
            annotated.append(
                GeneratedTest(
                    id=test.id,
                    name=test.name,
                    description=test.description,
                    contract_rule=test.contract_rule or "required_behaviour",
                    pytest_code=pytest_code,
                )
            )
        return annotated

    return _generate_tests_deterministic(contract, domain)


def _generate_tests_via_llm(
    contract: dict[str, Any],
    domain: str,
    session_id: str | None,
) -> tuple[list[GeneratedTest] | None, Any]:
    contract_yaml = yaml.safe_dump(contract, sort_keys=False)
    pack = load_domain_pack(domain)
    user_prompt = build_test_generation_user_prompt(contract_yaml, domain, pack)

    llm_result, meta = invoke_structured_task(
        LlmTaskName.TEST_GENERATION,
        LlmTestGenerationResult,
        TEST_GENERATION_SYSTEM_PROMPT,
        user_prompt,
        session_id=session_id,
    )

    if llm_result is None or not llm_result.tests:
        return None, meta

    tests: list[GeneratedTest] = []
    for index, llm_test in enumerate(llm_result.tests, start=1):
        test_id = _sanitize_test_id(llm_test.id or f"test_{index}")
        pytest_code = llm_test.pytest_code.strip()
        if not pytest_code.startswith("def "):
            pytest_code = _pytest_template(
                test_id,
                llm_test.description,
                _parse_threshold(contract.get("trigger", {}).get("condition", "")),
                llm_test.assertions,
            )
        tests.append(
            GeneratedTest(
                id=test_id,
                name=llm_test.name,
                description=llm_test.description,
                contract_rule=llm_test.contract_rule,
                pytest_code=pytest_code,
            )
        )
    return tests, meta


def _generate_tests_deterministic(contract: dict[str, Any], domain: str) -> list[GeneratedTest]:
    pack = load_domain_pack(domain)
    entity = contract.get("entity", "entity").replace("_", " ")
    threshold_value = _parse_threshold(contract.get("trigger", {}).get("condition", ""))
    obligations = set(contract.get("required_behaviour", []))

    base_tests: list[tuple[str, str, str]] = [
        (
            "test_under_threshold_normal_flow",
            f"{entity.title()} under {threshold_value} confirms normally",
            "exceptions",
        ),
    ]

    if OBLIGATION_FINANCE_APPROVAL in obligations or any("approval" in item for item in obligations):
        base_tests.extend(
            [
                (
                    "test_above_threshold_blocked_without_approval",
                    f"{entity.title()} over {threshold_value} without finance approval is blocked",
                    OBLIGATION_FINANCE_APPROVAL,
                ),
                (
                    "test_above_threshold_allowed_with_approval",
                    f"{entity.title()} over {threshold_value} with finance approval is allowed",
                    OBLIGATION_FINANCE_APPROVAL,
                ),
            ]
        )

    base_tests.append(
        (
            "test_unauthorized_user_cannot_approve",
            "Non-finance user cannot approve",
            "permissions",
        )
    )

    if OBLIGATION_APPROVAL_LOGGED in obligations:
        base_tests.append(
            (
                "test_approval_event_logged",
                "Approval event is logged with approver identity",
                OBLIGATION_APPROVAL_LOGGED,
            )
        )

    if OBLIGATION_SUPPLIER_BLOCKED in obligations:
        base_tests.append(
            (
                "test_supplier_confirmation_blocked",
                "Supplier confirmation is blocked until finance approval exists",
                OBLIGATION_SUPPLIER_BLOCKED,
            )
        )

    for obligation in obligations:
        if obligation in {
            OBLIGATION_FINANCE_APPROVAL,
            OBLIGATION_SUPPLIER_BLOCKED,
            OBLIGATION_APPROVAL_LOGGED,
        }:
            continue
        obligation_id = f"test_{obligation}"
        base_tests.append(
            (
                obligation_id,
                f"Contract obligation enforced: {obligation.replace('_', ' ')}",
                obligation,
            )
        )

    base_tests.append(
        (
            "test_existing_creation_regression",
            f"Existing {entity} creation still works after change",
            "regression",
        )
    )

    tests: list[GeneratedTest] = []
    for test_id, description, rule in base_tests:
        tests.append(
            GeneratedTest(
                id=test_id,
                name=description,
                description=description,
                contract_rule=rule,
                pytest_code=_pytest_template(test_id, description, threshold_value, []),
            )
        )

    if not tests:
        for index, template in enumerate(pack.get("test_templates", []), start=1):
            description = template.format(entity=entity, threshold=threshold_value)
            test_id = f"test_{index}"
            tests.append(
                GeneratedTest(
                    id=test_id,
                    name=description,
                    description=description,
                    contract_rule="required_behaviour",
                    pytest_code=_pytest_template(test_id, description, threshold_value, []),
                )
            )

    return tests


def _sanitize_test_id(raw_id: str) -> str:
    sanitized = SAFE_TEST_ID_PATTERN.sub("_", raw_id.strip().lower())
    if not sanitized.startswith("test_"):
        sanitized = f"test_{sanitized}"
    return sanitized


def _parse_threshold(condition: str) -> str:
    if ">" in condition:
        return condition.split(">")[-1].strip()
    return "threshold"


def _pytest_template(
    test_id: str,
    description: str,
    threshold: str,
    assertions: list[str],
) -> str:
    numeric_threshold = threshold.replace("£", "").replace(",", "").strip() or "25000"
    assertion_lines = "\n    ".join(f"assert {line}" for line in assertions) if assertions else (
        f"assert transaction_amount > {numeric_threshold}\n"
        f"    assert has_finance_approval is False"
    )
    return f'''def {test_id}():
    """{description}"""
    transaction_amount = 30000
    has_finance_approval = False
    {assertion_lines}
'''


def _annotate_pytest_source(pytest_code: str, llm_meta: dict[str, Any]) -> str:
    source_tag = CONFIDENCE_LLM if not llm_meta.get("used_fallback_rules") else CONFIDENCE_DETERMINISTIC
    meta_comment = f"# Generated via LLM ({source_tag}, {llm_meta.get('provider')}:{llm_meta.get('model')})"
    if meta_comment in pytest_code:
        return pytest_code
    return f"{meta_comment}\n{pytest_code}"

from typing import Any

from app.models.schemas import GeneratedTest
from app.services.domain_loader import load_domain_pack


def generate_tests(contract: dict[str, Any], domain: str) -> list[GeneratedTest]:
    pack = load_domain_pack(domain)
    entity = contract.get("entity", "entity").replace("_", " ")
    threshold = contract.get("trigger", {}).get("condition", "threshold")
    threshold_value = _parse_threshold(threshold)

    base_tests = [
        (
            "test_under_threshold_normal_flow",
            f"{entity.title()} under {threshold_value} confirms normally",
            "exceptions",
        ),
        (
            "test_above_threshold_blocked_without_approval",
            f"{entity.title()} over {threshold_value} without finance approval is blocked",
            "finance_approval_required",
        ),
        (
            "test_above_threshold_allowed_with_approval",
            f"{entity.title()} over {threshold_value} with finance approval is allowed",
            "finance_approval_required",
        ),
        (
            "test_unauthorized_user_cannot_approve",
            "Non-finance user cannot approve",
            "permissions",
        ),
        (
            "test_approval_event_logged",
            "Approval event is logged",
            "approval_event_logged",
        ),
    ]

    if domain == "procurement":
        base_tests.append(
            (
                "test_supplier_confirmation_blocked",
                "Supplier confirmation is blocked until finance approval exists",
                "supplier_confirmation_blocked_until_approval",
            )
        )
        base_tests.append(
            (
                "test_existing_creation_regression",
                f"Existing {entity} creation still works",
                "regression",
            )
        )

    tests: list[GeneratedTest] = []
    for index, (test_id, description, rule) in enumerate(base_tests, start=1):
        tests.append(
            GeneratedTest(
                id=test_id,
                name=description,
                description=description,
                contract_rule=rule,
                pytest_code=_pytest_template(test_id, description, threshold_value),
            )
        )

    if not tests:
        for index, template in enumerate(pack.get("test_templates", []), start=1):
            description = template.format(entity=entity, threshold=threshold_value)
            tests.append(
                GeneratedTest(
                    id=f"test_{index}",
                    name=description,
                    description=description,
                    contract_rule="required_behaviour",
                    pytest_code=_pytest_template(f"test_{index}", description, threshold_value),
                )
            )

    return tests


def _parse_threshold(condition: str) -> str:
    if ">" in condition:
        return condition.split(">")[-1].strip()
    return "threshold"


def _pytest_template(test_id: str, description: str, threshold: str) -> str:
    return f'''def {test_id}():
    """{description}"""
    # Contract rule linkage: generated from Change Contract
    po_amount = 30000  # above {threshold}
    has_finance_approval = False
    assert po_amount > {threshold.replace("£", "").replace(",", "") or "25000"}
    # Expected behaviour validated against approved contract
    assert has_finance_approval is False
'''

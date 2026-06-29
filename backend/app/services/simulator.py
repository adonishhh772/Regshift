from typing import Any

from app.models.schemas import SimulationCase


def run_simulation(contract: dict[str, Any], domain: str) -> dict[str, Any]:
    threshold = _get_threshold(contract, domain)

    if domain == "procurement":
        before = [
            SimulationCase(
                label="PO under threshold",
                amount=20000,
                approval="none",
                result="allowed",
                verdict="pass",
            ),
            SimulationCase(
                label="PO over threshold, no approval",
                amount=30000,
                approval="none",
                result="allowed",
                verdict="policy violation",
            ),
            SimulationCase(
                label="PO over threshold, finance approved",
                amount=30000,
                approval="finance",
                result="allowed",
                verdict="pass",
            ),
        ]
        after = [
            SimulationCase(
                label="PO under threshold",
                amount=20000,
                approval="none",
                result="allowed",
                verdict="pass",
            ),
            SimulationCase(
                label="PO over threshold, no approval",
                amount=30000,
                approval="none",
                result="blocked",
                verdict="pass",
            ),
            SimulationCase(
                label="PO over threshold, finance approved",
                amount=30000,
                approval="finance",
                result="allowed",
                verdict="pass",
            ),
        ]
    elif domain == "inventory":
        before, after = _inventory_simulation(threshold)
    elif domain == "hr_compliance":
        before, after = _hr_simulation(threshold)
    else:
        before, after = _generic_simulation(threshold)

    summary = (
        f"Before change: high-value transactions may bypass controls. "
        f"After change: transactions above {threshold:,} require approval before proceeding."
    )

    return {
        "before": before,
        "after": after,
        "summary": summary,
    }


def _get_threshold(contract: dict[str, Any], domain: str) -> int:
    condition = contract.get("trigger", {}).get("condition", "")
    if ">" in condition:
        try:
            return int(condition.split(">")[-1].strip())
        except ValueError:
            pass
    defaults = {
        "procurement": 25000,
        "inventory": 10000,
        "hr_compliance": 48,
    }
    return defaults.get(domain, 25000)


def _inventory_simulation(threshold: int) -> tuple[list[SimulationCase], list[SimulationCase]]:
    before = [
        SimulationCase(label="Transfer under threshold", amount=8000, approval="none", result="allowed", verdict="pass"),
        SimulationCase(label="Transfer over threshold", amount=12000, approval="none", result="allowed", verdict="policy violation"),
        SimulationCase(label="Transfer with approval", amount=12000, approval="warehouse_manager", result="allowed", verdict="pass"),
    ]
    after = [
        SimulationCase(label="Transfer under threshold", amount=8000, approval="none", result="allowed", verdict="pass"),
        SimulationCase(label="Transfer over threshold", amount=12000, approval="none", result="blocked", verdict="pass"),
        SimulationCase(label="Transfer with approval", amount=12000, approval="warehouse_manager", result="allowed", verdict="pass"),
    ]
    return before, after


def _hr_simulation(threshold: int) -> tuple[list[SimulationCase], list[SimulationCase]]:
    before = [
        SimulationCase(label="Under weekly hours", amount=40, approval="none", result="allowed", verdict="pass"),
        SimulationCase(label="Over weekly hours", amount=52, approval="none", result="allowed", verdict="policy violation"),
        SimulationCase(label="Over hours with review", amount=52, approval="manager", result="allowed", verdict="pass"),
    ]
    after = [
        SimulationCase(label="Under weekly hours", amount=40, approval="none", result="allowed", verdict="pass"),
        SimulationCase(label="Over weekly hours", amount=52, approval="none", result="blocked", verdict="pass"),
        SimulationCase(label="Over hours with review", amount=52, approval="manager", result="allowed", verdict="pass"),
    ]
    return before, after


def _generic_simulation(threshold: int) -> tuple[list[SimulationCase], list[SimulationCase]]:
    before = [
        SimulationCase(label="Below threshold", amount=threshold - 1000, approval="none", result="allowed", verdict="pass"),
        SimulationCase(label="Above threshold", amount=threshold + 5000, approval="none", result="allowed", verdict="policy violation"),
    ]
    after = [
        SimulationCase(label="Below threshold", amount=threshold - 1000, approval="none", result="allowed", verdict="pass"),
        SimulationCase(label="Above threshold", amount=threshold + 5000, approval="none", result="blocked", verdict="pass"),
    ]
    return before, after

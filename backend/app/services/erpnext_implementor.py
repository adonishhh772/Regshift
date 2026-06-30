import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.config import settings
from app.services.simulator import DOMAIN_DEFAULT_THRESHOLDS

REGSHIFT_MARKER_START = "# REGSHIFT:BEGIN"
REGSHIFT_MARKER_END = "# REGSHIFT:END"
JS_MARKER_START = "// REGSHIFT:BEGIN"
JS_MARKER_END = "// REGSHIFT:END"

ENTITY_PURCHASE_ORDER = "purchase_order"
DOMAIN_PROCUREMENT = "procurement"

PURCHASE_ORDER_PY_RELATIVE = "erpnext/buying/doctype/purchase_order/purchase_order.py"
PURCHASE_ORDER_JS_RELATIVE = "erpnext/buying/doctype/purchase_order/purchase_order.js"
PURCHASE_ORDER_TEST_RELATIVE = "erpnext/buying/doctype/purchase_order/test_purchase_order.py"


@dataclass(frozen=True)
class CodePatch:
    patch_id: str
    file_path: str
    obligation: str
    change_type: str
    description: str
    lines_added: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "file_path": self.file_path,
            "obligation": self.obligation,
            "change_type": self.change_type,
            "description": self.description,
            "lines_added": self.lines_added,
        }


def apply_change_contract_to_erpnext(session: dict[str, Any]) -> dict[str, Any]:
    contract = _load_contract(session)
    domain = contract.get("domain") or session.get("domain") or DOMAIN_PROCUREMENT
    entity = contract.get("entity", "")

    if domain != DOMAIN_PROCUREMENT or entity != ENTITY_PURCHASE_ORDER:
        return {
            "applied": False,
            "reason": f"Implementation scaffold available for {DOMAIN_PROCUREMENT}/{ENTITY_PURCHASE_ORDER} only",
            "patches": [],
            "repo_path": str(settings.erpnext_repo_path),
        }

    threshold = _resolve_threshold(contract, domain)
    obligations = list(contract.get("required_behaviour", []))
    approval_roles = list(contract.get("approval_roles", []))

    repo_root = settings.erpnext_repo_path
    repo_root.mkdir(parents=True, exist_ok=True)

    _bootstrap_purchase_order_scaffold(repo_root)

    patches: list[CodePatch] = []
    py_path = repo_root / PURCHASE_ORDER_PY_RELATIVE
    js_path = repo_root / PURCHASE_ORDER_JS_RELATIVE
    test_path = repo_root / PURCHASE_ORDER_TEST_RELATIVE

    py_block = _build_python_approval_block(threshold, obligations, approval_roles)
    py_patch = _inject_block(
        py_path,
        block_id="procurement_finance_approval",
        block=py_block,
        marker_style="python",
        hook_call="regshift_validate_finance_approval(self)\n        regshift_validate_supplier_confirmation_gate(self)",
        hook_method="validate",
    )
    if py_patch:
        patches.append(py_patch)

    js_block = _build_javascript_gate_block(threshold)
    js_patch = _inject_block(
        js_path,
        block_id="supplier_confirmation_gate",
        block=js_block,
        marker_style="javascript",
    )
    if js_patch:
        patches.append(js_patch)

    test_block = _build_test_block(threshold)
    test_patch = _inject_block(
        test_path,
        block_id="regshift_contract_tests",
        block=test_block,
        marker_style="python",
    )
    if test_patch:
        patches.append(test_patch)

    return {
        "applied": len(patches) > 0,
        "reason": None if patches else "No patches applied — blocks may already exist",
        "patches": [patch.to_dict() for patch in patches],
        "repo_path": str(repo_root),
        "threshold": threshold,
        "obligations": obligations,
    }


def _load_contract(session: dict[str, Any]) -> dict[str, Any]:
    contract_yaml = session.get("contract_yaml") or ""
    if contract_yaml:
        parsed = yaml.safe_load(contract_yaml)
        if isinstance(parsed, dict):
            return parsed
    contract_json = session.get("contract_json")
    if isinstance(contract_json, str) and contract_json.strip():
        import json

        parsed = json.loads(contract_json)
        if isinstance(parsed, dict):
            return parsed
    return {}


def _resolve_threshold(contract: dict[str, Any], domain: str) -> int:
    trigger = contract.get("trigger", {})
    condition = str(trigger.get("condition", ""))
    match = re.search(r"(\d[\d,]*)", condition)
    if match:
        return int(match.group(1).replace(",", ""))
    policy_threshold = contract.get("policy_threshold")
    if isinstance(policy_threshold, (int, float)):
        return int(policy_threshold)
    return DOMAIN_DEFAULT_THRESHOLDS.get(domain, 25000)


def ensure_erpnext_kg_seed(repo_root: Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    _bootstrap_purchase_order_scaffold(repo_root)


def _bootstrap_purchase_order_scaffold(repo_root: Path) -> None:
    py_path = repo_root / PURCHASE_ORDER_PY_RELATIVE
    if not py_path.exists():
        py_path.parent.mkdir(parents=True, exist_ok=True)
        py_path.write_text(
            '''import frappe
from frappe import _
from frappe.utils import flt
from erpnext.controllers.buying_controller import BuyingController


class PurchaseOrder(BuyingController):
    """Purchase order workflow with finance approval and supplier confirmation gates."""

    def validate(self):
        self.validate_supplier_after_submit()
        self.validate_minimum_order_qty()
        self.validate_finance_approval_for_high_value_orders()

    def validate_finance_approval_for_high_value_orders(self):
        threshold = flt(self.get("regshift_finance_approval_threshold") or 25000)
        if flt(self.grand_total) > threshold and not self.get("regshift_finance_approved"):
            frappe.throw(_("Finance approval required before supplier confirmation for high value purchase orders"))

    def on_submit(self):
        self.check_next_docstatus()
''',
            encoding="utf-8",
        )

    js_path = repo_root / PURCHASE_ORDER_JS_RELATIVE
    if not js_path.exists():
        js_path.parent.mkdir(parents=True, exist_ok=True)
        js_path.write_text(
            '''frappe.ui.form.on("Purchase Order", {
    refresh(frm) {
        frm.add_custom_button(__("Supplier Confirmation"), () => confirm_supplier(frm));
    },
});
''',
            encoding="utf-8",
        )

    test_path = repo_root / PURCHASE_ORDER_TEST_RELATIVE
    if not test_path.exists():
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(
            '''import frappe
from frappe.tests import IntegrationTestCase


class TestPurchaseOrder(IntegrationTestCase):
    pass
''',
            encoding="utf-8",
        )


def _build_python_approval_block(
    threshold: int,
    obligations: list[str],
    approval_roles: list[str],
) -> str:
    roles_literal = repr([role.lower().replace(" ", "_") for role in approval_roles])
    return f'''{REGSHIFT_MARKER_START} procurement_finance_approval
REGSHIFT_FINANCE_APPROVAL_THRESHOLD = {threshold}
REGSHIFT_APPROVAL_ROLES = {roles_literal}


def regshift_requires_finance_approval(doc):
    return flt(doc.get("grand_total") or 0) > REGSHIFT_FINANCE_APPROVAL_THRESHOLD


def regshift_validate_finance_approval(doc):
    if not regshift_requires_finance_approval(doc):
        return
    if not doc.get("regshift_finance_approved"):
        frappe.throw(
            _("Finance approval required for purchase orders above {{0}}").format(
                REGSHIFT_FINANCE_APPROVAL_THRESHOLD
            )
        )
    regshift_log_approval_event(doc)


def regshift_validate_supplier_confirmation_gate(doc):
    if not regshift_requires_finance_approval(doc):
        return
    if doc.get("regshift_supplier_confirmed") and not doc.get("regshift_finance_approved"):
        frappe.throw(_("Supplier confirmation blocked until finance approval is recorded"))


def regshift_log_approval_event(doc):
    if not doc.get("regshift_finance_approved"):
        return
    frappe.logger("regshift").info(
        "approval_event_logged purchase_order={{0}} approver={{1}}".format(
            doc.name,
            doc.get("regshift_approved_by") or frappe.session.user,
        )
    )


def regshift_user_can_approve(user=None):
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user))
    normalized = {{role.replace(" ", "_").lower() for role in roles}}
    return bool(normalized.intersection(set(REGSHIFT_APPROVAL_ROLES)))
{REGSHIFT_MARKER_END} procurement_finance_approval
'''


def _build_javascript_gate_block(threshold: int) -> str:
    return f'''{JS_MARKER_START} supplier_confirmation_gate
const REGSHIFT_FINANCE_APPROVAL_THRESHOLD = {threshold};

function regshift_can_confirm_supplier(frm) {{
    const total = flt(frm.doc.grand_total || 0);
    if (total <= REGSHIFT_FINANCE_APPROVAL_THRESHOLD) {{
        return true;
    }}
    return Boolean(frm.doc.regshift_finance_approved);
}}
{JS_MARKER_END} supplier_confirmation_gate
'''


def _build_test_block(threshold: int) -> str:
    return f'''{REGSHIFT_MARKER_START} regshift_contract_tests
def test_purchase_order_under_threshold_allowed():
    doc = {{"grand_total": {max(threshold - 5000, 1)}, "regshift_finance_approved": 0}}
    assert not regshift_requires_finance_approval(doc)


def test_purchase_order_over_threshold_requires_approval():
    doc = {{"grand_total": {threshold + 5000}, "regshift_finance_approved": 0}}
    assert regshift_requires_finance_approval(doc)
{REGSHIFT_MARKER_END} regshift_contract_tests
'''


def _inject_block(
    file_path: Path,
    block_id: str,
    block: str,
    marker_style: str,
    hook_call: str | None = None,
    hook_method: str | None = None,
) -> CodePatch | None:
    content = file_path.read_text(encoding="utf-8")
    start_marker = REGSHIFT_MARKER_START if marker_style == "python" else JS_MARKER_START
    block_marker = f"{start_marker} {block_id}"

    if block_marker in content:
        return None

    updated = content.rstrip() + "\n\n" + block.strip() + "\n"

    if hook_call and hook_method and hook_call.split("\n")[0] not in updated:
        hook_lines = "\n".join(f"        {line.strip()}" for line in hook_call.split("\n") if line.strip())
        anchor = "        self.validate_minimum_order_qty()\n"
        if anchor in updated:
            updated = updated.replace(anchor, anchor + hook_lines + "\n", 1)
        else:
            method_header = f"    def {hook_method}(self):"
            if method_header in updated:
                updated = updated.replace(
                    method_header,
                    method_header + "\n" + hook_lines,
                    1,
                )

    if marker_style == "javascript" and "regshift_can_confirm_supplier" in block:
        updated = updated.replace(
            'frm.add_custom_button(__("Supplier Confirmation"), () => confirm_supplier(frm));',
            'if (regshift_can_confirm_supplier(frm)) {\n            frm.add_custom_button(__("Supplier Confirmation"), () => confirm_supplier(frm));\n        }',
        )

    lines_added = len(updated.splitlines()) - len(content.splitlines())
    file_path.write_text(updated, encoding="utf-8")

    return CodePatch(
        patch_id=f"patch_{block_id}",
        file_path=str(file_path.relative_to(settings.erpnext_repo_path)).replace("\\", "/"),
        obligation=block_id,
        change_type=marker_style,
        description=f"Applied RegShift block '{block_id}' from change pack contract",
        lines_added=max(lines_added, 1),
    )

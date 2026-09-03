"""Work Item Type controller: validate measurement rules."""
from __future__ import annotations
import frappe
from frappe import _
from frappe.model.document import Document
from insite.calc.measures import MEASURE_KEYS, evaluate_formula

_SAMPLE = {"height": 1.0, "width": 1.0, "length": 1.0, "count": 1.0, "wastage": 1.0}


class WorkItemType(Document):
    def validate(self):
        for row in (self.measurement_rules or []):
            if row.measure not in MEASURE_KEYS:
                frappe.throw(_("Row {0}: unknown measure {1}").format(row.idx, row.measure))
            if row.measure == "formula":
                if not (row.formula or "").strip():
                    frappe.throw(_("Row {0}: choose a formula or a ready-made measure.").format(row.idx))
                try:
                    evaluate_formula(row.formula, _SAMPLE)
                except Exception as e:  # noqa: BLE001
                    frappe.throw(_("Row {0}: invalid formula — {1}").format(row.idx, str(e)))
            self._validate_scope(row)

    def _validate_scope(self, row):
        need = {"Item Code": "item_code", "Item Template": "item_template",
                "Item Group": "item_group", "Item Attribute Value": "item_attribute"}.get(row.apply_on)
        if need and not row.get(need):
            frappe.throw(_("Row {0}: choose what '{1}' applies to.").format(row.idx, row.apply_on))

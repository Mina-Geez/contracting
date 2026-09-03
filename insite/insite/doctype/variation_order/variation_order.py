"""Variation Order controller. On submit/cancel, recompute affected Scope Items."""
from __future__ import annotations
import frappe
from frappe import _
from frappe.model.document import Document


class VariationOrder(Document):
    def validate(self):
        for row in (self.variation_lines or []):
            if not row.scope_item:
                frappe.throw(_("Row {0}: choose a Scope.").format(row.idx))

    def on_submit(self):
        self._recompute_scopes()

    def on_cancel(self):
        self._recompute_scopes()

    def _recompute_scopes(self):
        names = {r.scope_item for r in (self.variation_lines or []) if r.scope_item}
        for name in names:
            frappe.get_doc("Scope Item", name).recompute_revised()

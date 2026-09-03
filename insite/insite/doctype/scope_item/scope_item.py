"""Scope Item controller. Revised = Original + Σ approved Variation deltas.

`recompute_revised()` is idempotent and called by Variation Order on submit/cancel
(documented save path, never db_set)."""
from __future__ import annotations
import frappe
from frappe.utils import flt
from frappe.model.document import Document


class ScopeItem(Document):
    def validate(self):
        self._apply_revised(save=False)

    def recompute_revised(self):
        """Recompute net variations + revised from submitted Variation Lines, then save."""
        self._apply_revised(save=False)
        self.save(ignore_permissions=True)

    def _apply_revised(self, save=False):
        net = frappe.db.sql(
            """
            select coalesce(sum(vl.delta_amount), 0)
            from `tabVariation Line` vl
            join `tabVariation Order` vo on vl.parent = vo.name
            where vl.scope_item = %s and vo.docstatus = 1
            """,
            (self.name,),
        )[0][0]
        self.net_variations_amount = flt(net)
        self.revised_planned_amount = flt(self.original_planned_amount) + flt(net)

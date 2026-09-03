"""Scope Item controller. Revised = Planned + the approved variations.

The revised amount is stored rather than derived so it can be read on the
record, in list views and in print formats. That makes it a read-modify-write,
so the row is locked before the total is taken — without the lock, two
Variation Orders submitted at the same moment each read their own rows only,
and the second write silently discards the first. The wrong figure would then
persist until someone happened to re-save the scope.
"""
from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class ScopeItem(Document):
	def validate(self):
		self._apply_revised()

	def recompute_revised(self):
		"""Re-total the approved variations and store the result."""
		self.save(ignore_permissions=True)  # validate() does the arithmetic

	def _apply_revised(self):
		net = flt(self._approved_variation_total())
		self.net_variations_amount = net
		self.revised_planned_amount = flt(self.original_planned_amount) + net

	def _approved_variation_total(self):
		if self.is_new():
			return 0.0
		# Lock this scope before reading, so a concurrent Variation Order
		# cannot compute its total from a snapshot that is about to change.
		frappe.db.get_value("Scope Item", self.name, "name", for_update=True)
		return frappe.db.sql(
			"""
			select coalesce(sum(line.delta_amount), 0)
			from `tabVariation Line` line
			join `tabVariation Order` vo on line.parent = vo.name
			where line.scope_item = %s and vo.docstatus = 1
			""",
			(self.name,),
		)[0][0]

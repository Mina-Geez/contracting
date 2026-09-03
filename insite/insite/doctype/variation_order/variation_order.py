"""Variation Order controller.

The Type column decides the direction of the change, so a user types a positive
amount and picks Add or Omit — they never have to remember a sign convention.
On submit or cancel, every scope the order touches is re-totalled.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

ADD = "Add"
OMIT = "Omit"
MODIFY = "Modify"


class VariationOrder(Document):
	def validate(self):
		for row in self.variation_lines or []:
			if not row.scope_item:
				frappe.throw(
					_("Row {0}: choose the Scope this change applies to.").format(row.idx),
					title=_("Scope Required"),
				)
			self._apply_direction(row)

	def on_submit(self):
		self._recompute_scopes()

	def on_cancel(self):
		self._recompute_scopes()

	def _apply_direction(self, row):
		"""Make the stored amount agree with the chosen Type.

		Add always increases the scope, Omit always reduces it. Modify is left
		exactly as typed, because either direction is legitimate there.
		"""
		amount, qty = flt(row.delta_amount), flt(row.delta_qty)
		if row.change_type == ADD:
			row.delta_amount, row.delta_qty = abs(amount), abs(qty)
		elif row.change_type == OMIT:
			row.delta_amount, row.delta_qty = -abs(amount), -abs(qty)

	def _recompute_scopes(self):
		for name in {row.scope_item for row in (self.variation_lines or []) if row.scope_item}:
			frappe.get_doc("Scope Item", name).recompute_revised()

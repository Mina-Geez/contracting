"""Whitelisted endpoints for client-side UX.

These are read-only: they resolve the applicable Calculation Rule and return the
computed quantity for live feedback in the item grid. The authoritative write
still happens in the server `before_validate` hook — the client merely mirrors it
via frappe.model.set_value so totals refresh immediately.
"""

import json

import frappe

from contracting.calc import engine


@frappe.whitelist()
def compute_row_qty(item_code: str, values=None):
	"""Return {qty, target_field, method, rule, inputs} or {skip: True}."""
	if not item_code:
		return {"skip": True}
	if isinstance(values, str):
		values = json.loads(values or "{}")
	return engine.compute_for_values(item_code, values or {})

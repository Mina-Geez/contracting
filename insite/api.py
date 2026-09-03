"""Whitelisted endpoints for the Insite desk UI."""
from __future__ import annotations

import frappe
from frappe import _

from insite.calc.measures import compute


@frappe.whitelist(methods=["POST"])
@frappe.rate_limit(limit=60, seconds=60)
def preview_measure(
	measure: str,
	height: float = 0,
	width: float = 0,
	length: float = 0,
	count: float = 1,
	wastage: float = 1,
	formula: str | None = None,
):
	"""Work out one quantity from sample measurements.

	Backs the "Test a Measure" button, so a rule can be checked before anyone
	relies on it. Reads nothing and writes nothing.
	"""
	frappe.only_for(["Contracting Manager", "System Manager"])
	try:
		return compute(measure, height=height, width=width, length=length,
		               count=count, wastage=wastage, formula=formula)
	except ValueError as e:
		frappe.throw(str(e), title=_("Measurement Problem"))
	except ArithmeticError:
		frappe.throw(
			_("That formula cannot be worked out with these measurements."),
			title=_("Measurement Problem"),
		)

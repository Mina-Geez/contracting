"""Whitelisted endpoints for the Insite desk UI."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from insite.calc.measures import evaluate_formula


@frappe.whitelist(methods=["POST"])
@frappe.rate_limit(limit=60, seconds=60)
def preview_formula(formula: str, values: str | dict | None = None):
	"""Work out one quantity from sample numbers.

	Backs the "Try it" button on a Measurement Rule, so a rule can be checked
	before anyone relies on it. Reads nothing and writes nothing.
	"""
	frappe.only_for(["Contracting Manager", "System Manager"])
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	numbers = {str(token): flt(value) for token, value in values.items()}
	try:
		return evaluate_formula(formula, numbers)
	except ValueError as e:
		frappe.throw(str(e), title=_("Formula Problem"))
	except ArithmeticError:
		frappe.throw(
			_("That formula cannot be worked out with these numbers."),
			title=_("Formula Problem"),
		)

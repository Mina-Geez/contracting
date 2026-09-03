"""Whitelisted endpoints for the Insite desk UI."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import flt

from insite.calc import engine
from insite.calc.measures import evaluate_formula
from insite.calc.resolve import resolve_rule


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=60, seconds=60)
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


@frappe.whitelist()
def inputs_for_item(item_code: str | None = None):
	"""Which measurement boxes this item's rule reads.

	The form asks as soon as an item is chosen, so a line only ever shows the
	boxes it needs — a door asks for height, width and a count, and does not
	offer a length nobody will fill in. Any user who can raise a document may
	ask; it reveals nothing beyond which fields to show.
	"""
	if not item_code:
		return ""

	rules = engine.load_rules()
	if not rules:
		return ""

	values = frappe.get_cached_value(
		"Item", item_code, ["item_group", "variant_of", "has_variants"], as_dict=True
	)
	if not values:
		return ""

	attributes = {
		row.attribute: row.attribute_value
		for row in frappe.get_all(
			"Item Variant Attribute",
			filters={"parent": item_code},
			fields=["attribute", "attribute_value"],
		)
	}
	item = {
		"item_code": item_code,
		"item_group": values.get("item_group"),
		"variant_of": values.get("variant_of"),
		"has_variants": values.get("has_variants"),
		"attributes": attributes,
	}
	rule = resolve_rule(item, rules)
	if not rule:
		return engine.NOTHING_MEASURED
	return ",".join(engine.line_fields_used(rule)) or engine.NOTHING_MEASURED

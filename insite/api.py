"""Whitelisted endpoints for the Insite desk UI."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import flt

from insite.calc import engine
from insite.calc.measures import MANUAL, evaluate_formula
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
def line_preview(item_code: str | None = None, values: str | dict | None = None):
	"""What a line needs, and what it comes to.

	The form asks as soon as an item is chosen and again as measurements are
	typed, so a line only shows the boxes it needs and the quantity keeps up
	with what someone is entering. The server decides again when the document
	is saved — this only saves the user from working blind until then.

	Any user who can raise a document may ask. It reveals nothing beyond which
	fields to show and the arithmetic they are already entitled to see.
	"""
	blank = {"inputs": "", "quantity": None, "rule": None}
	if not item_code:
		return blank

	rules = engine.load_rules()
	if not rules:
		return blank

	item = _item_for(item_code)
	if not item:
		return blank

	rule = resolve_rule(item, rules)
	if not rule:
		return {"inputs": engine.NOTHING_MEASURED, "quantity": None, "rule": None}

	answer = {
		"inputs": ",".join(engine.line_fields_used(rule)) or engine.NOTHING_MEASURED,
		"quantity": None,
		"rule": rule["title"],
	}
	if rule["preset"] == MANUAL:
		return answer

	line = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	numbers = engine.read_inputs(frappe._dict(line), rule, _item_values_for(item_code, rule))
	if not [value for value in numbers.values() if value]:
		return answer  # nothing measured yet
	try:
		answer["quantity"] = flt(evaluate_formula(rule["formula"], numbers), 3)
	except (ValueError, ArithmeticError):
		pass  # the rule is being edited, or the numbers do not work yet
	return answer


def _item_for(item_code):
	values = frappe.get_cached_value(
		"Item", item_code, ["item_group", "variant_of", "has_variants"], as_dict=True
	)
	if not values:
		return None
	attributes = {
		row.attribute: row.attribute_value
		for row in frappe.get_all(
			"Item Variant Attribute",
			filters={"parent": item_code},
			fields=["attribute", "attribute_value"],
		)
	}
	return {
		"item_code": item_code,
		"item_group": values.get("item_group"),
		"variant_of": values.get("variant_of"),
		"has_variants": values.get("has_variants"),
		"attributes": attributes,
	}


def _item_values_for(item_code, rule):
	fields = engine.item_fields_used(rule)
	if not fields:
		return {}
	return frappe.get_cached_value("Item", item_code, fields, as_dict=True) or {}

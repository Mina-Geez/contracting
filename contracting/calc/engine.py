"""Calculation Rule resolution + application (server-authoritative).

The engine resolves the single best Calculation Rule for a line item using a
most-specific-wins strategy (mirroring ERPNext Pricing Rule), then computes the
billable quantity via :mod:`contracting.calc.methods` and writes it onto the row.

All computation happens server-side (called from a ``before_validate`` doc event
in :mod:`contracting.overrides.transaction`) so that:
  * ERPNext's own ``validate`` -> ``calculate_taxes_and_totals`` runs afterwards
    and picks up the computed qty; and
  * rows inserted by ``get_mapped_doc`` (which never fire client triggers) are
    still calculated correctly.
"""

from __future__ import annotations

import json

import frappe
from frappe.utils import cint, flt

from contracting.calc import methods

# Specificity scores (higher = more specific). Priority breaks ties within a tier.
_SPECIFICITY = {
	"Item Code": 400,
	"Item Template": 300,
	"Item Attribute Value": 200,
	"Item Group": 100,
}

_RULE_FIELDS = [
	"name",
	"rule_name",
	"disabled",
	"priority",
	"apply_on",
	"item_code",
	"item_template",
	"item_attribute",
	"attribute_value",
	"item_group",
	"calculation_method",
	"formula",
	"height_field",
	"width_field",
	"length_field",
	"qty_multiplier_field",
	"waste_factor_field",
	"waste_factor_value",
	"target_field",
	"qty_precision",
]


def has_enabled_rules() -> bool:
	"""Cheap gate so non-contracting sites/documents skip all work."""
	return bool(frappe.get_all("Calculation Rule", filters={"disabled": 0}, limit=1))


def load_enabled_rules() -> list[frappe._dict]:
	"""All enabled rules, ordered so the first match within a tier is preferred."""
	return frappe.get_all(
		"Calculation Rule",
		filters={"disabled": 0},
		fields=_RULE_FIELDS,
		order_by="priority desc, modified desc",
	)


def _item_meta(item_code: str) -> frappe._dict | None:
	if not item_code:
		return None
	values = frappe.get_cached_value(
		"Item", item_code, ["item_group", "variant_of", "has_variants"], as_dict=True
	)
	return values or None


def _make_attr_getter():
	"""Lazily fetch (and cache) an item's variant attributes as {attribute: value}."""
	cache: dict[str, dict] = {}

	def getter(item_code: str) -> dict:
		if item_code not in cache:
			rows = frappe.get_all(
				"Item Variant Attribute",
				filters={"parent": item_code},
				fields=["attribute", "attribute_value"],
			)
			cache[item_code] = {r.attribute: r.attribute_value for r in rows}
		return cache[item_code]

	return getter


def _match_score(rule, item, item_code, attr_getter) -> int:
	"""Return the specificity score if ``rule`` applies to the item, else -1."""
	apply_on = rule.apply_on

	if apply_on == "Item Code":
		return _SPECIFICITY[apply_on] if rule.item_code and rule.item_code == item_code else -1

	if apply_on == "Item Template":
		template = item.variant_of or (item_code if item.has_variants else None)
		return _SPECIFICITY[apply_on] if rule.item_template and rule.item_template == template else -1

	if apply_on == "Item Attribute Value":
		if not rule.item_attribute:
			return -1
		value = attr_getter(item_code).get(rule.item_attribute)
		if value is not None and str(value) == str(rule.attribute_value):
			return _SPECIFICITY[apply_on]
		return -1

	if apply_on == "Item Group":
		return _SPECIFICITY[apply_on] if rule.item_group and rule.item_group == item.item_group else -1

	return -1


def resolve_rule_for_item(item_code: str, rules: list, attr_getter=None) -> frappe._dict | None:
	"""Pick the most-specific applicable rule for ``item_code`` (None if none)."""
	item = _item_meta(item_code)
	if not item:
		return None
	if attr_getter is None:
		attr_getter = _make_attr_getter()

	best, best_specificity = None, -1
	for rule in rules:
		score = _match_score(rule, item, item_code, attr_getter)
		# Rules arrive pre-sorted by priority desc, modified desc; the first rule
		# at the highest specificity therefore already carries the top priority.
		if score > best_specificity:
			best, best_specificity = rule, score
	return best


def _dim(row, fieldname: str) -> float:
	return flt(row.get(fieldname)) if fieldname else 0.0


def _resolve_inputs(row, rule) -> dict:
	"""Read the dimension inputs for ``rule`` from a line ``row`` (or value dict)."""
	base_qty = _dim(row, rule.qty_multiplier_field) if rule.qty_multiplier_field else 0.0
	if not base_qty:
		base_qty = flt(row.get("custom_base_qty"))
	if not base_qty:
		base_qty = 1.0  # no count given -> single unit

	waste_factor = _dim(row, rule.waste_factor_field) if rule.waste_factor_field else 0.0
	if not waste_factor:
		waste_factor = flt(rule.waste_factor_value) or 1.0

	return {
		"height": _dim(row, rule.height_field),
		"width": _dim(row, rule.width_field),
		"length": _dim(row, rule.length_field),
		"base_qty": base_qty,
		"waste_factor": waste_factor,
	}


def compute_qty_for_row(row, rule):
	"""Return (qty, inputs) for a row+rule without mutating the row.

	``qty`` is None for the manual method. Shared by the server hook and the
	client-facing API so both use identical logic.
	"""
	inputs = _resolve_inputs(row, rule)
	qty = methods.compute(rule.calculation_method, formula=rule.formula, **inputs)
	return qty, inputs


def apply_rule_to_row(row, rule) -> None:
	"""Compute and write the billable qty (+ audit fields) onto a line ``row``."""
	qty, inputs = compute_qty_for_row(row, rule)

	# Audit trail (always recorded, even for manual, so reports/debug can trace).
	row.set("custom_calc_method", rule.calculation_method)
	row.set("custom_calc_rule", rule.name)
	row.set("custom_calc_dimensions", json.dumps(inputs))

	if qty is None:
		# manual method: leave user-entered qty untouched.
		return

	precision = cint(rule.qty_precision) or 3
	qty = flt(qty, precision)
	row.set(rule.target_field or "qty", qty)
	row.set("custom_calculated_qty", qty)


def compute_for_values(item_code: str, values: dict) -> dict:
	"""Client-facing: compute qty for a set of row values (no DB writes).

	Returns {qty, target_field, method, rule, inputs} or {skip: True} when no
	rule matches or the method is manual.
	"""
	rules = load_enabled_rules()
	rule = resolve_rule_for_item(item_code, rules)
	if not rule:
		return {"skip": True}

	row = frappe._dict(values or {})
	qty, inputs = compute_qty_for_row(row, rule)
	if qty is None:
		return {"skip": True, "method": rule.calculation_method, "rule": rule.name}

	precision = cint(rule.qty_precision) or 3
	return {
		"qty": flt(qty, precision),
		"target_field": rule.target_field or "qty",
		"method": rule.calculation_method,
		"rule": rule.name,
		"inputs": inputs,
	}


def recalculate_document(doc) -> int:
	"""Recompute every applicable line on ``doc``. Returns rows affected.

	Safe no-op when the document has no item table or no enabled rules exist.
	"""
	items = doc.get("items")
	if not items:
		return 0
	if not has_enabled_rules():
		return 0

	rules = load_enabled_rules()
	if not rules:
		return 0

	attr_getter = _make_attr_getter()
	affected = 0
	for row in items:
		if not row.get("item_code"):
			continue
		rule = resolve_rule_for_item(row.item_code, rules, attr_getter)
		if rule:
			apply_rule_to_row(row, rule)
			affected += 1
	return affected

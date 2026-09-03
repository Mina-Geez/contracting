"""Frappe glue around the pure calc core: load rules, resolve, apply to rows.

The engine is deliberately conservative about touching a user's quantity. It
writes one only when a rule matches AND the measurements it needs are actually
filled in. When a rule stops matching a line — the item changed, the rule was
deleted — it clears what it previously wrote, so a stale quantity can never
outlive the rule that produced it.
"""
from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from insite.calc import measures
from insite.calc.resolve import resolve_rule

TARGET_FIELD = "qty"
DEFAULT_PRECISION = 3

#: Fields the engine owns on a transaction line.
_AUDIT_FIELDS = ("custom_calculated_qty", "custom_calc_measure",
                 "custom_calc_source", "custom_calc_dimensions")

#: The inputs each measure actually reads. A row with none of them filled in
#: has not been measured, so the engine leaves the typed quantity alone.
_REQUIRED_INPUTS = {
	measures.AREA: ("height", "width"),
	measures.PERIMETER: ("height", "width"),
	measures.LINEAR: ("length",),
	measures.COUNT: ("count",),
	measures.PIECE_WASTE: ("count",),
}


def load_rules():
	"""Every rule on every enabled Work Item Type, most important first."""
	rules = []
	types = frappe.get_all("Work Item Type", filters={"disabled": 0},
	                       fields=["name"], order_by="modified desc")
	for entry in types:
		doc = frappe.get_cached_doc("Work Item Type", entry.name)
		for row in doc.measurement_rules:
			rules.append({
				"source": doc.name,
				"measure": measures.normalize_measure(row.measure),
				"formula": row.formula,
				"apply_on": row.apply_on, "item_code": row.item_code,
				"item_template": row.item_template, "item_group": row.item_group,
				"item_attribute": row.item_attribute, "attribute_value": row.attribute_value,
				"priority": cint(row.priority),
			})
	rules.sort(key=lambda r: r["priority"], reverse=True)  # stable: keeps modified-desc within a tier
	return rules


def compute_qty_for_row(row, rule):
	"""Return (qty, inputs) for a row and rule. qty is None for `manual`."""
	inputs = _inputs(row)
	qty = measures.compute(rule["measure"], formula=rule.get("formula"), **inputs)
	return qty, inputs


def apply_rule_to_row(row, rule):
	"""Write the measured quantity and the audit trail onto `row`."""
	inputs = _inputs(row)
	if not _has_measurements(rule["measure"], inputs):
		# Nothing was measured on this line — leave the user's quantity alone
		# and do not claim the line was measured.
		_clear_calc_fields(row)
		return None

	try:
		qty = measures.compute(rule["measure"], formula=rule.get("formula"), **inputs)
	except ValueError as e:
		frappe.throw(
			_("Row {0}: {1}").format(row.idx, str(e)),
			title=_("Measurement Problem"),
		)
	except ArithmeticError:
		frappe.throw(
			_("Row {0}: the formula on {1} cannot be worked out with these measurements ({2}).").format(
				row.idx, rule["source"], _describe(inputs)),
			title=_("Measurement Problem"),
		)

	row.set("custom_calc_measure", measures.MEASURE_LABELS.get(rule["measure"], rule["measure"]))
	row.set("custom_calc_source", rule["source"])
	row.set("custom_calc_dimensions", json.dumps(inputs))

	if qty is None:  # manual: keep the typed quantity, and do not leave a stale one behind
		row.set("custom_calculated_qty", None)
		return None

	precision = _precision(row)
	rounded = flt(qty, precision)
	previous = flt(row.get(TARGET_FIELD))
	row.set(TARGET_FIELD, rounded)
	# Unrounded, so the audit trail can still show what the engine really computed.
	row.set("custom_calculated_qty", qty)
	return (previous, rounded) if flt(previous, precision) != rounded else None


def recalculate_document(doc):
	"""Recompute every measured line on `doc`. Returns the number changed."""
	items = doc.get("items")
	if not items:
		return 0

	rules = load_rules()
	attributes = _attributes_for(items) if rules else {}
	changes = []

	for row in items:
		rule = None
		if rules and row.get("item_code"):
			item = _item_context(row.item_code, attributes)
			if item:
				rule = resolve_rule(item, rules)
		if rule:
			change = apply_rule_to_row(row, rule)
			if change:
				changes.append((row.idx, change[0], change[1], rule["source"]))
		else:
			# No rule applies any more. Anything the engine wrote before must go,
			# or the line keeps a quantity and an audit trail it no longer earns.
			_clear_calc_fields(row)

	if changes:
		_report_changes(changes)
	return len(changes)


def _report_changes(changes):
	"""Tell the user which quantities the engine changed, and from what."""
	lines = [
		_("Row {0}: {1} → {2} ({3})").format(idx, before, after, source)
		for idx, before, after, source in changes[:10]
	]
	if len(changes) > 10:
		lines.append(_("… and {0} more").format(len(changes) - 10))
	frappe.msgprint(
		"<br>".join(lines),
		title=_("Quantities recalculated from measurements"),
		indicator="blue",
	)


def _clear_calc_fields(row):
	for field in _AUDIT_FIELDS:
		if row.get(field):
			row.set(field, None)


def _has_measurements(measure, inputs):
	needed = _REQUIRED_INPUTS.get(measure)
	if not needed:  # manual and formula decide for themselves
		return True
	return any(inputs.get(name) for name in needed)


def _precision(row):
	try:
		return cint(row.precision(TARGET_FIELD)) or DEFAULT_PRECISION
	except Exception:
		return DEFAULT_PRECISION


def _describe(inputs):
	return ", ".join(f"{name.title()} {value:g}" for name, value in inputs.items() if value)


def _inputs(row):
	return {
		"height": flt(row.get("custom_height")),
		"width": flt(row.get("custom_width")),
		"length": flt(row.get("custom_length")),
		"count": flt(row.get("custom_base_qty")),
		"wastage": flt(row.get("custom_waste_factor")),
	}


def _item_context(item_code, attributes):
	values = frappe.get_cached_value("Item", item_code,
	                                 ["item_group", "variant_of", "has_variants"], as_dict=True)
	if not values:
		return None
	return {
		"item_code": item_code,
		"item_group": values.get("item_group"),
		"variant_of": values.get("variant_of"),
		"has_variants": values.get("has_variants"),
		"attributes": attributes.get(item_code, {}),
	}


def _attributes_for(items):
	"""Fetch variant attributes for every item on the document in one query."""
	codes = {row.item_code for row in items if row.get("item_code")}
	if not codes:
		return {}
	rows = frappe.get_all("Item Variant Attribute",
	                      filters={"parent": ["in", list(codes)]},
	                      fields=["parent", "attribute", "attribute_value"])
	grouped: dict[str, dict] = {}
	for row in rows:
		grouped.setdefault(row.parent, {})[row.attribute] = row.attribute_value
	return grouped

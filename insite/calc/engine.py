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
_AUDIT_FIELDS = (
	"custom_calculated_qty",
	"custom_calc_measure",
	"custom_calc_source",
	"custom_calc_dimensions",
)


def load_rules():
	"""Every enabled rule whose Work Item Type is also enabled, most important first."""
	enabled_types = set(frappe.get_all("Work Item Type", filters={"disabled": 0}, pluck="name"))
	if not enabled_types:
		return []

	rules = []
	names = frappe.get_all(
		"Measurement Rule",
		filters={"disabled": 0, "work_item_type": ["in", list(enabled_types)]},
		pluck="name",
		order_by="modified desc",
	)
	for name in names:
		doc = frappe.get_cached_doc("Measurement Rule", name)
		rules.append(
			{
				"source": doc.work_item_type,
				"rule": doc.name,
				"title": doc.rule_title or doc.name,
				"preset": doc.preset,
				"formula": doc.formula,
				# token -> the field on the line that supplies it
				"inputs": {row.token: row.field_name for row in doc.inputs},
				"apply_on": doc.apply_on,
				"item_code": doc.item_code,
				"item_template": doc.item_template,
				"item_group": doc.item_group,
				"item_attribute": doc.item_attribute,
				"attribute_value": doc.attribute_value,
				"priority": cint(doc.priority),
			}
		)
	rules.sort(key=lambda r: r["priority"], reverse=True)  # stable: keeps modified-desc within a tier
	return rules


def read_inputs(row, rule):
	"""{token: value} for a rule, read off the transaction line."""
	return {token: flt(row.get(fieldname)) for token, fieldname in rule["inputs"].items()}


def apply_rule_to_row(row, rule):
	"""Write the measured quantity and the audit trail onto `row`."""
	if rule["preset"] == measures.MANUAL:
		# The rule exists to say "do not calculate this". Record that, and leave
		# the typed quantity exactly as it is.
		_stamp(row, rule, {})
		row.set("custom_calculated_qty", None)
		return None

	values = read_inputs(row, rule)
	if not any(values.values()):
		# Nothing was measured on this line — leave the user's quantity alone
		# and do not claim the line was measured.
		_clear_calc_fields(row)
		return None

	try:
		qty = measures.evaluate_formula(rule["formula"], values)
	except ValueError as e:
		frappe.throw(_("Row {0}: {1}").format(row.idx, str(e)), title=_("Measurement Problem"))
	except ArithmeticError:
		frappe.throw(
			_("Row {0}: the formula on {1} cannot be worked out with these measurements ({2}).").format(
				row.idx, rule["source"], _describe(values)
			),
			title=_("Measurement Problem"),
		)

	_stamp(row, rule, values)

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
	no_longer_measured = []

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
			# or the line keeps an audit trail it no longer earns. The quantity
			# is left alone — it is the user's field, and ERPNext keeps it too
			# when an item changes — but they are told to look at it.
			if row.get("custom_calc_source"):
				no_longer_measured.append((row.idx, row.get("item_code"), flt(row.get(TARGET_FIELD))))
			_clear_calc_fields(row)

	if changes:
		_report_changes(changes)
	if no_longer_measured:
		_report_no_longer_measured(no_longer_measured)
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


def _report_no_longer_measured(rows):
	"""Warn when a line stops being measured but keeps its old quantity.

	The quantity is not reset — it belongs to the user — so the only safe thing
	is to say plainly that nothing is calculating it any more.
	"""
	lines = [
		_("Row {0} ({1}): quantity is still {2}").format(idx, item_code or "", quantity)
		for idx, item_code, quantity in rows[:10]
	]
	frappe.msgprint(
		"<br>".join(lines),
		title=_("These lines are no longer measured — check the quantity"),
		indicator="orange",
	)


def _stamp(row, rule, values):
	"""Record which rule ran and what it read, so a quantity can be traced."""
	row.set("custom_calc_measure", rule["title"])
	row.set("custom_calc_source", rule["source"])
	row.set("custom_calc_dimensions", json.dumps(values))


def _clear_calc_fields(row):
	for field in _AUDIT_FIELDS:
		if row.get(field):
			row.set(field, None)


def _precision(row):
	try:
		return cint(row.precision(TARGET_FIELD)) or DEFAULT_PRECISION
	except Exception:
		return DEFAULT_PRECISION


def _describe(values):
	return ", ".join(f"{name} {value:g}" for name, value in values.items() if value)


def _item_context(item_code, attributes):
	values = frappe.get_cached_value(
		"Item", item_code, ["item_group", "variant_of", "has_variants"], as_dict=True
	)
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
	rows = frappe.get_all(
		"Item Variant Attribute",
		filters={"parent": ["in", list(codes)]},
		fields=["parent", "attribute", "attribute_value"],
	)
	grouped: dict[str, dict] = {}
	for row in rows:
		grouped.setdefault(row.parent, {})[row.attribute] = row.attribute_value
	return grouped

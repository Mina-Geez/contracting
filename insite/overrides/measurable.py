"""Tick Measurable on an Item Group, a Brand or an Item, and the rule is written.

A Measurement Rule stays its own record. That is what lets one rule cover a
group, a brand, a template or a single item, what gives the ladder something to
order, and what a second rule on the same target would break. None of that is
worth explaining to somebody setting up an item group.

So the record carries the two things a person actually decides — **is this
measured**, and **how** — and Insite keeps the rule in step with them. The rule
is still the authority: it holds the inputs, the formula, any further numbers
the measurements give, and the priority. These fields are the front door to the
common case, and `refresh_from_rule` puts them straight when someone has been in
through the back one.
"""

from __future__ import annotations

import frappe
from frappe import _

from insite.calc.measures import MANUAL, PRESET_CHOICES
from insite.insite.doctype.measurement_rule.measurement_rule import get_preset

#: The record a rule can be written from, and the Applies To it becomes.
MEASURABLE_FROM = {
	"Item Group": ("Item Group", "item_group"),
	"Brand": ("Brand", "brand"),
	"Item": ("Item Code", "item_code"),
}


def sync_rule(doc, method=None):
	"""Keep this record's own rule in step with the two fields on its form."""
	if doc.doctype not in MEASURABLE_FROM:
		return
	if not doc.meta.has_field("custom_measurable"):
		return  # migrate has not added the fields yet

	rule = _own_rule(doc)

	if not doc.get("custom_measurable"):
		_stop_measuring(rule)
		_show(doc, None)
		return

	preset = doc.get("custom_measurement_preset")
	if preset not in PRESET_CHOICES:
		frappe.throw(
			_("Choose how {0} is measured, or untick Measurable.").format(doc.name),
			title=_("How Is It Measured?"),
		)

	rule = _write_rule(doc, rule, preset)
	_show(doc, rule)


def refresh_from_rule(doc, method=None):
	"""Put the form's fields straight from the rule, which is the authority.

	A rule disabled or repointed on its own form would otherwise leave this
	record claiming something that is no longer true.
	"""
	if doc.doctype not in MEASURABLE_FROM or not doc.meta.has_field("custom_measurable"):
		return

	rule = _own_rule(doc)
	live = rule and not rule.disabled
	doc.custom_measurable = 1 if live else 0
	doc.custom_measurement_preset = rule.preset if live else None
	doc.custom_measurement_summary = (rule.measurement_summary or "") if live else None


def _own_rule(doc):
	"""This record's own rule — not one inherited from a parent item group.

	Inheritance is the resolver's business. Here the question is narrower: does
	a rule point at this record, and is the checkbox telling the truth about it.
	"""
	apply_on, field = MEASURABLE_FROM[doc.doctype]
	name = frappe.db.get_value("Measurement Rule", {"apply_on": apply_on, field: doc.name}, "name")
	return frappe.get_doc("Measurement Rule", name) if name else None


def _write_rule(doc, rule, preset):
	apply_on, field = MEASURABLE_FROM[doc.doctype]
	if rule is None:
		rule = frappe.new_doc("Measurement Rule")
		rule.apply_on = apply_on
		rule.set(field, doc.name)
	elif rule.preset == preset and not rule.disabled:
		return rule  # nothing to say

	rule.disabled = 0
	rule.preset = preset
	# Changing the starting point replaces the arithmetic it came with. Anything
	# hand-written is edited on the rule, where it is visible.
	rule.set("inputs", [])
	rule.formula = None
	if preset != MANUAL:
		starting_point = get_preset(preset)
		rule.formula = starting_point.get("formula")
		for row in starting_point.get("inputs") or []:
			rule.append("inputs", {"source": "Line", **row})

	rule.save(ignore_permissions=True)
	return rule


def _stop_measuring(rule):
	"""Disable rather than delete: a rule may have been written on for months."""
	if rule and not rule.disabled:
		rule.db_set("disabled", 1, update_modified=False)


def _show(doc, rule):
	"""Write the summary back without saving the document again."""
	summary = (rule.measurement_summary or "") if rule else None
	if doc.get("custom_measurement_summary") != summary:
		doc.db_set("custom_measurement_summary", summary, update_modified=False)

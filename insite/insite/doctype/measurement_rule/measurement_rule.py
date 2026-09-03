"""Measurement Rule — for these items, read these fields and combine them like this.

Everything is checked when the rule is saved, so a rule that could never work
is refused while the person who wrote it is still looking at it, rather than
failing later on somebody else's Sales Order.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from insite.calc import measures
from insite.config.available_fields import field_label, measurable_fields

_SCOPE_FIELDS = {
	"Item Code": ("item_code", "Item"),
	"Item Template": ("item_template", "Item Template"),
	"Item Group": ("item_group", "Item Group"),
	"Item Attribute Value": ("item_attribute", "Attribute"),
}


class MeasurementRule(Document):
	def validate(self):
		self._validate_scope()
		self._validate_inputs()
		self._validate_formula()
		self._set_title()

	# --- scope ---------------------------------------------------------------

	def _validate_scope(self):
		field, label = _SCOPE_FIELDS.get(self.apply_on, (None, None))
		if field and not self.get(field):
			frappe.throw(
				_("Applies To is set to {0}. Fill in the {1} box.").format(self.apply_on, label),
				title=_("Scope Required"),
			)
		if self.apply_on == "Item Attribute Value" and not (self.attribute_value or "").strip():
			frappe.throw(
				_("Fill in the Attribute Value. A rule with no value can never match a line."),
				title=_("Attribute Value Required"),
			)

	# --- inputs --------------------------------------------------------------

	def _validate_inputs(self):
		if self.preset == measures.MANUAL:
			return

		allowed = measurable_fields()
		seen = set()
		for row in self.inputs or []:
			if row.field_name not in allowed:
				frappe.throw(
					_(
						"Row {0}: '{1}' is not a number field on the transaction line. "
						"Pick one from the list."
					).format(row.idx, row.field_name),
					title=_("Unknown Field"),
				)
			row.field_label = allowed[row.field_name]

			if not row.token:
				row.token = measures.suggest_token(row.field_label)
			if not measures.is_valid_token(row.token):
				frappe.throw(
					_(
						"Row {0}: '{1}' cannot be used in a formula. Use lower case letters, "
						"digits and underscores, for example number_of_panels."
					).format(row.idx, row.token),
					title=_("Invalid Name"),
				)
			if row.token in seen:
				frappe.throw(
					_("Row {0}: the name '{1}' is used twice. Each input needs its own name.").format(
						row.idx, row.token
					),
					title=_("Duplicate Name"),
				)
			seen.add(row.token)

	# --- formula -------------------------------------------------------------

	def _validate_formula(self):
		if self.preset == measures.MANUAL:
			self.formula = None
			return

		if not (self.formula or "").strip():
			frappe.throw(
				_("Write a formula, or choose a different starting point."),
				title=_("Formula Required"),
			)
		if not self.inputs:
			frappe.throw(
				_("Add at least one input. A formula has nothing to read without one."),
				title=_("Inputs Required"),
			)
		try:
			measures.validate_formula(self.formula, {row.token for row in self.inputs})
		except ValueError as e:
			frappe.throw(str(e), title=_("Formula Problem"))

		unused = {row.token for row in self.inputs} - measures.formula_tokens(self.formula)
		if unused:
			frappe.msgprint(
				_("The formula does not use: {0}. Remove the input, or use it in the formula.").format(
					", ".join(sorted(unused))
				),
				title=_("Unused Input"),
				indicator="orange",
			)

	# --- naming --------------------------------------------------------------

	def _set_title(self):
		target = self.get(_SCOPE_FIELDS.get(self.apply_on, ("", ""))[0]) or ""
		if self.apply_on == "Item Attribute Value":
			target = f"{self.item_attribute} = {self.attribute_value}"
		self.rule_title = f"{self.work_item_type} · {target}" if target else self.work_item_type


@frappe.whitelist()
def get_measurable_fields():
	"""Fields the Inputs grid may choose from, newest-friendly first."""
	frappe.only_for(["Contracting Manager", "System Manager"])
	return [{"value": name, "label": label} for name, label in measurable_fields().items()]


@frappe.whitelist()
def get_preset(name: str):
	"""The inputs and formula a preset starts from."""
	frappe.only_for(["Contracting Manager", "System Manager"])
	preset = measures.PRESETS.get(name)
	if not preset:
		return {"inputs": [], "formula": ""}
	return {
		"inputs": [
			{"field_name": fieldname, "field_label": field_label(fieldname), "token": token}
			for token, fieldname in preset["inputs"]
		],
		"formula": preset["formula"],
	}

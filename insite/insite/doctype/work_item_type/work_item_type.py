"""Work Item Type controller: check the measurement rules make sense.

Everything here is caught at save time, so a rule that could never work is
rejected while the person who wrote it is still looking at it — rather than
failing later on somebody else's Sales Order.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from insite.calc import measures

#: Which field has to be filled in for each kind of scope.
_SCOPE_FIELDS = {
	"Item Code": ("item_code", "Item"),
	"Item Template": ("item_template", "Item Template"),
	"Item Group": ("item_group", "Item Group"),
	"Item Attribute Value": ("item_attribute", "Attribute"),
}


class WorkItemType(Document):
	def validate(self):
		for row in self.measurement_rules or []:
			self._validate_measure(row)
			self._validate_scope(row)

	def _validate_measure(self, row):
		# The row stores the name a person picked; the engine works in keys.
		# Normalise a copy only — writing the key back onto the row would fail
		# the Select validation that Frappe runs after this method.
		measure = measures.normalize_measure(row.measure)
		if measure not in measures.MEASURE_KEYS:
			frappe.throw(
				_(
					"Row {0}: '{1}' is not a measure Insite knows. Choose a value from the Measured By list."
				).format(row.idx, row.measure),
				title=_("Unknown Measure"),
			)
		if measure != measures.FORMULA:
			return
		if not (row.formula or "").strip():
			frappe.throw(
				_(
					"Row {0}: Measured By is set to Custom formula, but the Formula box is empty. "
					"Write a formula, or choose a ready-made measure."
				).format(row.idx),
				title=_("Formula Required"),
			)
		try:
			measures.validate_formula(row.formula)
		except ValueError as e:
			frappe.throw(_("Row {0}: {1}").format(row.idx, str(e)), title=_("Formula Problem"))

	def _validate_scope(self, row):
		field, label = _SCOPE_FIELDS.get(row.apply_on, (None, None))
		if field and not row.get(field):
			frappe.throw(
				_("Row {0}: Applies To is set to {1}. Fill in the {2} box.").format(
					row.idx, row.apply_on, label
				),
				title=_("Scope Required"),
			)
		if row.apply_on == "Item Attribute Value" and not (row.attribute_value or "").strip():
			frappe.throw(
				_(
					"Row {0}: fill in the Attribute Value. A rule with no value can never match a line."
				).format(row.idx),
				title=_("Attribute Value Required"),
			)

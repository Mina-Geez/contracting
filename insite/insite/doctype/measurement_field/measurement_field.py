"""Measurement Field — a number a site measures that Insite does not ship.

Name it once here and Insite adds it to every sales and purchase line, so a
rule can read it wherever the work is quoted, ordered, delivered or invoiced.
Adding it to only one document type is the trap this exists to prevent: a rule
would work on a Sales Order and quietly compute nothing on the invoice.

The field is created with the same idempotent helper Insite uses for its own
fields, so `bench migrate` re-asserts it and nothing drifts.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.model.document import Document

from insite.config.available_fields import INSITE_FIELDS
from insite.constants import ITEM_DOCTYPES

#: New fields sit at the end of the Measurements section Insite already draws.
INSERT_AFTER = "custom_waste_factor"

PREFIX = "custom_"


class MeasurementField(Document):
	def validate(self):
		self._set_field_name()
		self._check_not_reserved()
		self.used_by = ", ".join(using_field(self.field_name)) or None

	def on_update(self):
		self.apply()

	def on_trash(self):
		self._block_if_used()
		remove_field(self.field_name, self.target_doctypes)

	# --- naming --------------------------------------------------------------

	def _set_field_name(self):
		if self.field_name:
			return  # never rename an existing field: data lives under that name
		slug = frappe.scrub(self.field_label or "")
		if not slug:
			frappe.throw(_("Give the field a label."), title=_("Label Required"))
		self.field_name = f"{PREFIX}{slug}"[:63]

	def _check_not_reserved(self):
		if self.field_name in INSITE_FIELDS:
			frappe.throw(
				_("Insite already has a field called {0}. Choose another label.").format(self.field_label),
				title=_("Name Already Used"),
			)
		clash = frappe.db.exists(
			"Custom Field", {"dt": ITEM_DOCTYPES[1], "fieldname": self.field_name, "name": ("!=", "")}
		)
		if clash and self.is_new():
			frappe.throw(
				_("A field named {0} already exists on the transaction line.").format(self.field_name),
				title=_("Name Already Used"),
			)

	# --- the fields themselves ------------------------------------------------

	@property
	def target_doctypes(self):
		"""Item-level numbers live on the material; the rest live on every line."""
		return ("Item",) if self.applies_to == "Item" else ITEM_DOCTYPES

	def apply(self):
		"""Create or update this field where it belongs."""
		definition = {
			"fieldname": self.field_name,
			"label": self.field_label,
			"fieldtype": "Float",
			"insert_after": INSERT_AFTER if self.applies_to != "Item" else "stock_uom",
			"description": self.help_text or "",
			"hidden": 1 if self.hidden else 0,
		}
		create_custom_fields(
			{doctype: [definition] for doctype in self.target_doctypes}, ignore_validate=True
		)

	# --- deletion -------------------------------------------------------------

	def _block_if_used(self):
		rules = using_field(self.field_name)
		if rules:
			frappe.throw(
				_(
					"{0} is used by: {1}. Change those rules first, or tick 'Hide on documents' instead."
				).format(self.field_label, ", ".join(rules)),
				title=_("Field In Use"),
			)


def using_field(field_name):
	"""Titles of the Measurement Rules that read `field_name`."""
	rules = frappe.get_all(
		"Measurement Input", filters={"field_name": field_name}, fields=["parent"], pluck="parent"
	)
	if not rules:
		return []
	return frappe.get_all("Measurement Rule", filters={"name": ("in", set(rules))}, pluck="rule_title")


def remove_field(field_name, doctypes=ITEM_DOCTYPES):
	"""Take the field off wherever it was added."""
	for doctype in doctypes:
		name = frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field_name})
		if name:
			frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)


def apply_all():
	"""Re-assert every site-defined field. Runs on install and every migrate."""
	for name in frappe.get_all("Measurement Field", pluck="name"):
		frappe.get_cached_doc("Measurement Field", name).apply()

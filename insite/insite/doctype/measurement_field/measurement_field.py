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

#: New fields sit at the end of the Measurements section Insite already draws,
#: after the last shipped box (Wastage).
INSERT_AFTER = "custom_waste_factor"

#: The section break that opens the (collapsed) Calculated section. Site fields
#: must land *before* it — see `reflow_measurement_section`.
CALC_SECTION_BREAK = "custom_insite_calc_sb"

PREFIX = "custom_"


class MeasurementField(Document):
	def validate(self):
		self._set_field_name()
		self._check_not_reserved()
		self.used_by = ", ".join(using_field(self.field_name)) or None

	def on_update(self):
		self.apply()

	def on_trash(self):
		self._block_if_shipped()
		self._block_if_used()
		self._block_if_it_holds_measurements()
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
		if self.is_standard:
			return  # these ARE Insite's own, recorded so they show in the list
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
		"""Create or update this field where it belongs.

		A shipped box is not applied from here. `config/custom_fields.py` owns
		those: it puts them in the Measurements section in a deliberate order,
		with the `depends_on` that hides the ones a line's rule does not read.
		Re-asserting them from this record would move them to the end of the
		section and drop that layout. The record exists so the list shows every
		measurable number in one place, and so a shipped one can be hidden.
		"""
		if self.is_standard:
			_hide_or_show(self.field_name, self.target_doctypes, self.hidden)
			return

		definition = {
			"fieldname": self.field_name,
			"label": self.field_label,
			"fieldtype": "Float",
			"insert_after": INSERT_AFTER if self.applies_to != "Item" else "stock_uom",
			"description": self.help_text or "",
			"hidden": 1 if self.hidden else 0,
		}
		if self.applies_to != "Item":
			# Show it only on lines whose rule reads it, exactly as Insite's own
			# measurement boxes behave.
			definition["depends_on"] = (
				"eval:!doc.custom_measurement_inputs "
				f"|| doc.custom_measurement_inputs.includes('{self.field_name}')"
			)
		create_custom_fields(
			{doctype: [definition] for doctype in self.target_doctypes}, ignore_validate=True
		)
		if self.applies_to != "Item":
			# The field was created after Wastage, where the Calculated section
			# break also sits. Chain the site fields and push the break past
			# them, so a second field can never land inside the Calculated
			# section, invisible and impossible to type into.
			reflow_measurement_section()

	# --- deletion -------------------------------------------------------------

	def _block_if_shipped(self):
		"""The boxes Insite ships stay. Documents everywhere hold values in them."""
		if self.is_standard:
			frappe.throw(
				_(
					"{0} is one of the boxes Insite ships and cannot be deleted. Tick 'Hide on documents' to take it off the forms."
				).format(self.field_label),
				title=_("Shipped With Insite"),
			)

	def _block_if_used(self):
		rules = using_field(self.field_name)
		if rules:
			frappe.throw(
				_(
					"{0} is used by: {1}. Change those rules first, or tick 'Hide on documents' instead."
				).format(self.field_label, ", ".join(rules)),
				title=_("Field In Use"),
			)

	def _block_if_it_holds_measurements(self):
		"""Refuse while any document still holds a number in this field.

		Deleting the Measurement Field deletes the Custom Field, and deleting a
		Custom Field drops its column — with every measurement anyone ever
		entered in it, on submitted documents, with no undo. Blocking only when
		a *rule* reads the field was never enough: a field nothing measures by
		any more can still be the only record of what was measured.
		"""
		holding = [doctype for doctype in self.target_doctypes if _holds_a_value(doctype, self.field_name)]
		if holding:
			frappe.throw(
				_(
					"{0} still holds measurements on {1}. Tick 'Hide on documents' to take it off the forms without losing them."
				).format(self.field_label, ", ".join(_(doctype) for doctype in holding)),
				title=_("Field Holds Data"),
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
	# The section break now sits after one fewer field; close the gap.
	reflow_measurement_section()


def transaction_line_site_fields():
	"""Site-defined transaction-line fields, oldest first.

	The order is by creation, not by `modified`, so the chain is stable: a field
	edited today does not jump ahead of one added before it.
	"""
	return frappe.get_all(
		"Measurement Field",
		filters={"is_standard": 0, "applies_to": ["!=", "Item"]},
		order_by="creation asc",
		pluck="field_name",
	)


def reflow_measurement_section(doctypes=ITEM_DOCTYPES):
	"""Chain site fields after Wastage and keep the Calculated break after them.

	Every site field was inserted after `custom_waste_factor`, and so was the
	Calculated section break. When both claimed that one slot, the second site
	field resolved *after* the break — inside the collapsed Calculated section,
	where its box could not be typed into. Silent, and it killed the app's
	headline feature (a number Insite does not ship).

	So the site fields are chained one after another off Wastage, and the break
	is moved to sit after the last of them (or back onto Wastage when a site
	removes them all). Idempotent: it only writes an anchor that is wrong.
	"""
	reference = doctypes[0] if doctypes else ITEM_DOCTYPES[0]
	# Only fields that still have a live Custom Field belong in the chain. On
	# deletion `remove_field` drops the Custom Field before this runs while the
	# Measurement Field row is still present (on_trash is before the delete), so
	# a name read from the master alone would anchor the break onto a field that
	# no longer exists.
	site_fields = [
		field_name
		for field_name in transaction_line_site_fields()
		if frappe.db.exists("Custom Field", {"dt": reference, "fieldname": field_name})
	]

	anchor = INSERT_AFTER
	chain = []
	for field_name in site_fields:
		chain.append((field_name, anchor))
		anchor = field_name

	touched = set()
	for doctype in doctypes:
		for field_name, after in chain:
			if _set_insert_after(doctype, field_name, after):
				touched.add(doctype)
		# The break follows the last site field, or Wastage when there are none.
		if _set_insert_after(doctype, CALC_SECTION_BREAK, anchor):
			touched.add(doctype)

	for doctype in touched:
		frappe.clear_cache(doctype=doctype)


def _set_insert_after(doctype, field_name, after):
	"""Point one Custom Field's `insert_after` at `after`. Returns whether it moved."""
	name = frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field_name})
	if not name or frappe.db.get_value("Custom Field", name, "insert_after") == after:
		return False
	frappe.db.set_value("Custom Field", name, "insert_after", after, update_modified=False)
	return True


def _holds_a_value(doctype, field_name):
	"""Does any row anywhere hold a number in this field? One query, stops at one."""
	if not frappe.db.has_column(doctype, field_name):
		return False
	return bool(
		frappe.db.sql(f"select name from `tab{doctype}` where ifnull(`{field_name}`, 0) != 0 limit 1")
	)


def _hide_or_show(field_name, doctypes, hidden):
	"""The one property of a shipped box this record owns."""
	for doctype in doctypes:
		name = frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field_name})
		if name and frappe.db.get_value("Custom Field", name, "hidden") != (1 if hidden else 0):
			frappe.db.set_value("Custom Field", name, "hidden", 1 if hidden else 0)
			frappe.clear_cache(doctype=doctype)


#: The boxes Insite ships, recorded so the master lists every measurable number
#: in one place — the way UOM ships its own and a site adds more. The fieldnames
#: must never change: documents hold measurements under them.
STANDARD_FIELDS = (
	("custom_base_qty", "Count", "How many units or pieces."),
	("custom_height", "Height", ""),
	("custom_width", "Width", ""),
	("custom_length", "Length", ""),
	(
		"custom_waste_factor",
		"Wastage",
		"How much to add for waste. Type 1.1 to add 10 percent. Leave blank for none.",
	),
)


def ensure_standard_fields():
	"""Record the shipped boxes in the master. Idempotent; runs on every migrate."""
	for field_name, label, help_text in STANDARD_FIELDS:
		if frappe.db.exists("Measurement Field", {"field_name": field_name}):
			continue
		doc = frappe.new_doc("Measurement Field")
		doc.update(
			{
				"field_label": label,
				"field_name": field_name,
				"applies_to": "Transaction line",
				"help_text": help_text,
				"is_standard": 1,
			}
		)
		doc.insert(ignore_permissions=True)


def apply_all():
	"""Re-assert every site-defined field. Runs on install and every migrate.

	Applied oldest first so the chain is asserted in the order the fields were
	created, then the whole Measurements section is reflowed once at the end —
	which also puts the Calculated break back in its place after a migrate has
	re-created it at `custom_waste_factor`.
	"""
	for name in frappe.get_all("Measurement Field", order_by="creation asc", pluck="name"):
		frappe.get_cached_doc("Measurement Field", name).apply()
	reflow_measurement_section()

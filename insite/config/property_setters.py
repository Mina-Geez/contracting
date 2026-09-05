"""Code-defined Property Setters (idempotent).

Some of what Insite needs to tune sits on fields, and doctypes, it does not own:
`qty` is a standard ERPNext field, `scope_item` on the ledger-posting tables is
created by the Accounting Dimension machinery, and the print format default is a
property of ERPNext's own selling doctypes. Editing those directly would fight
whoever owns them, so their properties are adjusted with Property Setters
instead — the documented way to override one property without taking it over.

Applied on install and every migrate, and upserted so re-running leaves exactly
one Property Setter per (doctype, field, property) rather than a fresh one each
time. Kept out of fixtures for the same reason as the custom fields: the setup
is code, reproducible from an empty site.
"""

from __future__ import annotations

import frappe

from insite.constants import MEASURED_DOCTYPES

#: Each selling document defaults to Insite's own print format — the one built to
#: show the scope and the measurement behind every quantity. Without it a
#: Quotation printed as "Quotation with Item Image": four glass sizes as four
#: identical lines with no sizes at all. The format itself already exists.
_DEFAULT_PRINT_FORMATS = {
	"Quotation": "Insite Quotation",
	"Sales Order": "Insite Sales Order",
	"Delivery Note": "Insite Delivery Note",
	"Sales Invoice": "Insite Sales Invoice",
}


def _field_setters():
	"""(doctype, fieldname, property, value, property_type) on a field."""
	setters = []
	for parent in MEASURED_DOCTYPES:
		child = f"{parent} Item"
		# Once a rule has worked out the quantity, it comes from the measurements
		# and nowhere else. Five reviewers typed a quantity, saw it accepted, and
		# watched the server replace it on save — so a measured line's qty is
		# read-only. A line with no calculated quantity (ordinary sales, or a
		# manual rule) is untouched and stays editable.
		setters.append((child, "qty", "read_only_depends_on", "eval:doc.custom_calculated_qty", "Data"))
		# The Scope belongs in the grid, not behind the row expander. On Quotation
		# Item it is Insite's own custom field and carries this already; here it is
		# the dimension-created field.
		setters.append((child, "scope_item", "in_list_view", "1", "Check"))
		setters.append((child, "scope_item", "columns", "2", "Int"))
	return setters


def _doctype_setters():
	"""(doctype, property, value, property_type) on a doctype itself."""
	return [(dt, "default_print_format", fmt, "Data") for dt, fmt in _DEFAULT_PRINT_FORMATS.items()]


def ensure_property_setters():
	for doctype, fieldname, prop, value, property_type in _field_setters():
		_upsert(doctype, prop, value, property_type, fieldname=fieldname)
	for doctype, prop, value, property_type in _doctype_setters():
		_upsert(doctype, prop, value, property_type)


def _upsert(doctype, prop, value, property_type, fieldname=None):
	doctype_or_field = "DocField" if fieldname else "DocType"
	filters = {"doc_type": doctype, "property": prop, "doctype_or_field": doctype_or_field}
	if fieldname:
		filters["field_name"] = fieldname

	existing = frappe.db.get_value("Property Setter", filters, "name")
	if existing:
		if frappe.db.get_value("Property Setter", existing, "value") != value:
			frappe.db.set_value("Property Setter", existing, "value", value)
		return

	args = {
		"doctype": doctype,
		"doctype_or_field": doctype_or_field,
		"property": prop,
		"value": value,
		"property_type": property_type,
	}
	if fieldname:
		args["fieldname"] = fieldname
	frappe.make_property_setter(args, is_system_generated=False, validate_fields_for_doctype=False)

"""Code-defined Property Setters (idempotent).

Some of what Insite needs to tune sits on fields it does not own: `qty` is a
standard ERPNext field, and `scope_item` on the ledger-posting tables is created
by the Accounting Dimension machinery. Editing those fields directly would fight
whoever does own them, so their properties are adjusted with Property Setters
instead — the documented way to override one field property without taking the
field over.

Applied on install and every migrate, and upserted so re-running leaves exactly
one Property Setter per (doctype, field, property) rather than a fresh one each
time. Kept out of fixtures for the same reason as the custom fields: the setup
is code, reproducible from an empty site.
"""

from __future__ import annotations

import frappe

from insite.constants import MEASURED_DOCTYPES


def _wanted():
	"""Every (doctype, fieldname, property, value, property_type) Insite sets."""
	setters = []
	for parent in MEASURED_DOCTYPES:
		child = f"{parent} Item"
		# Once a rule has worked out the quantity, it comes from the measurements
		# and nowhere else. Five reviewers typed a quantity, saw it accepted, and
		# watched the server replace it on save — so a measured line's qty is
		# read-only. A line with no calculated quantity (ordinary sales, or a
		# manual rule) is untouched and stays editable.
		setters.append((child, "qty", "read_only_depends_on", "eval:doc.custom_calculated_qty", "Data"))
		# The Scope belongs in the grid, not behind the row expander. It is
		# mandatory on measured lines, and forty lines should not be forty clicks
		# to check it. On Quotation Item the field is Insite's own custom field
		# and carries this already; here it is the dimension-created field.
		setters.append((child, "scope_item", "in_list_view", "1", "Check"))
		setters.append((child, "scope_item", "columns", "2", "Int"))
	return setters


def ensure_property_setters():
	for doctype, fieldname, prop, value, property_type in _wanted():
		_upsert(doctype, fieldname, prop, value, property_type)


def _upsert(doctype, fieldname, prop, value, property_type):
	existing = frappe.db.get_value(
		"Property Setter",
		{"doc_type": doctype, "field_name": fieldname, "property": prop},
		"name",
	)
	if existing:
		if frappe.db.get_value("Property Setter", existing, "value") != value:
			frappe.db.set_value("Property Setter", existing, "value", value)
		return
	frappe.make_property_setter(
		{
			"doctype": doctype,
			"fieldname": fieldname,
			"property": prop,
			"value": value,
			"property_type": property_type,
		},
		is_system_generated=False,
		validate_fields_for_doctype=False,
	)

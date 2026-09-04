"""Measurement Register — every line supplied against a scope, and how it was measured.

Contract Progress answers where a scope stands. This answers what it is made
of: each line, the measurements behind its quantity, and the description that
was on the item at the time.

That last column is the point for a specification argument. A developer changes
the ironmongery standard mid-job and the question becomes which deliveries were
made to the old one. Nothing new has to be recorded to answer it — ERPNext
already versions the Item, and every line keeps its own copy of the description
from the moment it was raised. The record existed and nobody could read it.

Documents are read with `get_list` so a reader only sees what their permissions
allow, and the lines are then fetched for those documents alone.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from insite.config.accounting_dimension import DIMENSION_FIELDNAME as SCOPE_FIELD

#: What a contractor supplies against a scope, in the order it happens.
SOURCES = (
	("Sales Order", "Sales Order Item", "transaction_date"),
	("Delivery Note", "Delivery Note Item", "posting_date"),
	("Sales Invoice", "Sales Invoice Item", "posting_date"),
)

#: The measurement boxes, and how each reads in a sentence.
MEASUREMENTS = (
	("custom_base_qty", "Count"),
	("custom_height", "H"),
	("custom_width", "W"),
	("custom_length", "L"),
	("custom_waste_factor", "Wastage"),
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Scope"),
			"fieldname": "scope",
			"fieldtype": "Link",
			"options": "Scope Item",
			"width": 180,
		},
		{
			"label": _("Document"),
			"fieldname": "document",
			"fieldtype": "Dynamic Link",
			"options": "doctype",
			"width": 160,
		},
		{"label": _("Type"), "fieldname": "doctype", "fieldtype": "Data", "width": 110},
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Measured"), "fieldname": "measured", "fieldtype": "Data", "width": 200},
		{"label": _("Quantity"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": _("Rate"), "fieldname": "rate", "fieldtype": "Currency", "width": 110},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Specification at the time"),
			"fieldname": "description",
			"fieldtype": "Small Text",
			"width": 300,
		},
	]


def get_data(filters):
	rows = []
	for doctype, child_doctype, date_field in SOURCES:
		if filters.get("document_type") and filters.document_type != doctype:
			continue
		rows.extend(_lines(doctype, child_doctype, date_field, filters))

	rows.sort(key=lambda row: (row["scope"] or "", row["date"] or "", row["document"]))
	return rows


def _lines(doctype, child_doctype, date_field, filters):
	"""Submitted lines carrying a scope, for documents the reader may see."""
	conditions = {"docstatus": 1}
	for field in ("company", "project"):
		if filters.get(field):
			conditions[field] = filters.get(field)
	if filters.get("from_date"):
		conditions[date_field] = [">=", filters.from_date]

	documents = frappe.get_list(doctype, filters=conditions, fields=["name", date_field], limit_page_length=0)
	if not documents:
		return []

	dates = {d.name: d.get(date_field) for d in documents}
	line_filters = {"parent": ["in", list(dates)], SCOPE_FIELD: ["is", "set"]}
	if filters.get("scope_item"):
		line_filters[SCOPE_FIELD] = filters.scope_item

	lines = frappe.get_all(
		child_doctype,
		filters=line_filters,
		fields=[
			"parent",
			"item_code",
			"description",
			"qty",
			"rate",
			"amount",
			SCOPE_FIELD,
			*[field for field, _label in MEASUREMENTS],
		],
		order_by="parent asc, idx asc",
	)

	return [
		{
			"scope": line.get(SCOPE_FIELD),
			"document": line.parent,
			"doctype": doctype,
			"date": dates.get(line.parent),
			"item_code": line.item_code,
			"measured": _in_words(line),
			"qty": flt(line.qty),
			"rate": flt(line.rate),
			"amount": flt(line.amount),
			"description": _plain(line.description),
		}
		for line in lines
	]


def _in_words(line):
	"""'H 1.500 × W 2.800 × 40 off' — only the boxes that were filled in."""
	parts = []
	for field, label in MEASUREMENTS:
		value = flt(line.get(field))
		if not value:
			continue
		parts.append(f"{label} {value:g}" if label != "Count" else f"{value:g} off")
	return " × ".join(parts)


def _plain(description):
	"""A description is a Text Editor field, and a report cell is not HTML."""
	if not description:
		return ""
	text = frappe.utils.strip_html(description).strip()
	return " ".join(text.split())

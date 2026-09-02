"""Code-defined Custom Fields for standard ERPNext item child tables.

Defined in code and applied idempotently via ``create_custom_fields`` in
after_install / after_migrate / patches — NOT shipped as fixtures of the standard
``Custom Field`` doctype, and NEVER via the destructive Export-Customizations
(``custom/*.json``) sync. This is the pattern ERPNext itself uses.

The dimension fields (height/width/length/base_qty/waste_factor) are generic
INPUTS. A Calculation Rule points at whichever of these (or any pre-existing
site field, e.g. the glass site's ``custom_عدد_الالواح``) holds each dimension;
the engine writes the computed billable qty back to ``qty`` (or the rule's
target field) and records an audit trail in the read-only calc fields.
"""

from __future__ import annotations

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

# Sales + purchase line-item child tables that carry dimension-driven quantities.
ITEM_DOCTYPES = [
	"Quotation Item",
	"Sales Order Item",
	"Delivery Note Item",
	"Sales Invoice Item",
	"Material Request Item",
	"Supplier Quotation Item",
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
]


def _item_fields() -> list[dict]:
	"""The identical field set applied to every item child table."""
	return [
		{
			"fieldname": "custom_contracting_dim_sb",
			"label": "Contracting — Dimensions",
			"fieldtype": "Section Break",
			"insert_after": "uom",
			"collapsible": 1,
		},
		{
			"fieldname": "custom_base_qty",
			"label": "Base Qty / Count",  # bilingual note: عدد الوحدات / الألواح
			"fieldtype": "Float",
			"insert_after": "custom_contracting_dim_sb",
			"description": "Physical unit count (panels/pieces). Input to the calculation engine.",
		},
		{
			"fieldname": "custom_height",
			"label": "Height",
			"fieldtype": "Float",
			"insert_after": "custom_base_qty",
		},
		{
			"fieldname": "custom_width",
			"label": "Width",
			"fieldtype": "Float",
			"insert_after": "custom_height",
		},
		{
			"fieldname": "custom_contracting_dim_cb",
			"fieldtype": "Column Break",
			"insert_after": "custom_width",
		},
		{
			"fieldname": "custom_length",
			"label": "Length",
			"fieldtype": "Float",
			"insert_after": "custom_contracting_dim_cb",
		},
		{
			"fieldname": "custom_waste_factor",
			"label": "Waste Factor",
			"fieldtype": "Float",
			"insert_after": "custom_length",
			"description": "Optional multiplier for offcut/waste allowance (defaults to 1).",
		},
		{
			"fieldname": "custom_contracting_calc_sb",
			"label": "Contracting — Calculation",
			"fieldtype": "Section Break",
			"insert_after": "custom_waste_factor",
			"collapsible": 1,
		},
		{
			"fieldname": "custom_calculated_qty",
			"label": "Calculated Qty",
			"fieldtype": "Float",
			"insert_after": "custom_contracting_calc_sb",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_calc_method",
			"label": "Calc Method",
			"fieldtype": "Data",
			"insert_after": "custom_calculated_qty",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_contracting_calc_cb",
			"fieldtype": "Column Break",
			"insert_after": "custom_calc_method",
		},
		{
			"fieldname": "custom_calc_rule",
			"label": "Calc Rule",
			"fieldtype": "Data",
			"insert_after": "custom_contracting_calc_cb",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_calc_dimensions",
			"label": "Calc Dimensions (JSON)",
			"fieldtype": "Small Text",
			"insert_after": "custom_calc_rule",
			"read_only": 1,
			"hidden": 1,
			"no_copy": 1,
		},
	]


def get_custom_fields() -> dict:
	"""Return the {doctype: [field, ...]} mapping for create_custom_fields."""
	fields = _item_fields()
	return {dt: fields for dt in ITEM_DOCTYPES}


def ensure_custom_fields() -> None:
	"""Idempotently create/update the contracting custom fields."""
	create_custom_fields(get_custom_fields(), ignore_validate=True)

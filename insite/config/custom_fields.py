"""Code-defined Custom Fields for ERPNext item child tables (idempotent).

Applied through `create_custom_fields` in after_install / after_migrate — never
as fixtures, never through Export-Customizations. Fieldnames are stable and
owned by the app; only the labels are human-facing and translated.

The product vocabulary maps to these fieldnames as follows, and nowhere else:
`custom_base_qty` is **Count**, `custom_waste_factor` is **Wastage**.
"""
from __future__ import annotations

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from insite.constants import ITEM_DOCTYPES


def _fields():
	return [
		{"fieldname": "custom_insite_dim_sb", "label": "Measurements",
		 "fieldtype": "Section Break", "insert_after": "uom", "collapsible": 1},
		{"fieldname": "custom_base_qty", "label": "Count", "fieldtype": "Float",
		 "insert_after": "custom_insite_dim_sb",
		 "description": "How many units or pieces."},
		{"fieldname": "custom_height", "label": "Height", "fieldtype": "Float",
		 "insert_after": "custom_base_qty"},
		{"fieldname": "custom_width", "label": "Width", "fieldtype": "Float",
		 "insert_after": "custom_height"},
		{"fieldname": "custom_insite_dim_cb", "fieldtype": "Column Break",
		 "insert_after": "custom_width"},
		{"fieldname": "custom_length", "label": "Length", "fieldtype": "Float",
		 "insert_after": "custom_insite_dim_cb"},
		{"fieldname": "custom_waste_factor", "label": "Wastage", "fieldtype": "Float",
		 "insert_after": "custom_length",
		 "description": "How much to add for waste. Type 1.1 to add 10 percent. Leave blank for none."},
		{"fieldname": "custom_insite_calc_sb", "label": "Calculated",
		 "fieldtype": "Section Break", "insert_after": "custom_waste_factor", "collapsible": 1},
		{"fieldname": "custom_calculated_qty", "label": "Calculated Quantity",
		 "fieldtype": "Float", "insert_after": "custom_insite_calc_sb",
		 "read_only": 1, "no_copy": 1},
		{"fieldname": "custom_calc_measure", "label": "Measure Used", "fieldtype": "Data",
		 "insert_after": "custom_calculated_qty", "read_only": 1, "no_copy": 1},
		{"fieldname": "custom_insite_calc_cb", "fieldtype": "Column Break",
		 "insert_after": "custom_calc_measure"},
		{"fieldname": "custom_calc_source", "label": "Work Item Type", "fieldtype": "Data",
		 "insert_after": "custom_insite_calc_cb", "read_only": 1, "no_copy": 1},
		{"fieldname": "custom_calc_dimensions", "label": "Measurements Used",
		 "fieldtype": "Small Text", "insert_after": "custom_calc_source",
		 "read_only": 1, "hidden": 1, "no_copy": 1},
	]


def get_custom_fields():
	fields = _fields()
	return {doctype: fields for doctype in ITEM_DOCTYPES}


def ensure_custom_fields():
	create_custom_fields(get_custom_fields(), ignore_validate=True)

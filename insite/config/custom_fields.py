"""Code-defined Custom Fields for ERPNext item child tables (idempotent).

Applied via create_custom_fields in after_install/after_migrate/patch — never
as fixtures, never via Export-Customizations. Fieldnames are stable and
app-owned; only labels are human/bilingual.
"""
from __future__ import annotations
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ITEM_DOCTYPES = [
    "Quotation Item", "Sales Order Item", "Delivery Note Item", "Sales Invoice Item",
    "Material Request Item", "Supplier Quotation Item", "Purchase Order Item",
    "Purchase Receipt Item", "Purchase Invoice Item",
]


def _fields():
    return [
        {"fieldname": "custom_insite_dim_sb", "label": "Insite — Measurements",
         "fieldtype": "Section Break", "insert_after": "uom", "collapsible": 1},
        {"fieldname": "custom_base_qty", "label": "Count", "fieldtype": "Float",
         "insert_after": "custom_insite_dim_sb",
         "description": "Number of units/pieces. Input to the measurement engine."},
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
         "description": "Optional wastage allowance multiplier (defaults to 1)."},
        {"fieldname": "custom_insite_calc_sb", "label": "Insite — Calculated",
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
        {"fieldname": "custom_calc_dimensions", "label": "Calc Inputs (JSON)",
         "fieldtype": "Small Text", "insert_after": "custom_calc_source",
         "read_only": 1, "hidden": 1, "no_copy": 1},
    ]


def get_custom_fields():
    fields = _fields()
    return {dt: fields for dt in ITEM_DOCTYPES}


def ensure_custom_fields():
    create_custom_fields(get_custom_fields(), ignore_validate=True)

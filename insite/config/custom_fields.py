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
		{
			"fieldname": "custom_insite_dim_sb",
			"label": "Measurements",
			"fieldtype": "Section Break",
			"insert_after": "uom",
			"collapsible": 1,
		},
		{
			"fieldname": "custom_base_qty",
			"depends_on": "eval:!doc.custom_measurement_inputs || doc.custom_measurement_inputs.includes('custom_base_qty')",
			"label": "Count",
			"fieldtype": "Float",
			"insert_after": "custom_insite_dim_sb",
			"description": "How many units or pieces.",
		},
		{
			"fieldname": "custom_height",
			"depends_on": "eval:!doc.custom_measurement_inputs || doc.custom_measurement_inputs.includes('custom_height')",
			"label": "Height",
			"fieldtype": "Float",
			"insert_after": "custom_base_qty",
		},
		{
			"fieldname": "custom_width",
			"depends_on": "eval:!doc.custom_measurement_inputs || doc.custom_measurement_inputs.includes('custom_width')",
			"label": "Width",
			"fieldtype": "Float",
			"insert_after": "custom_height",
		},
		{"fieldname": "custom_insite_dim_cb", "fieldtype": "Column Break", "insert_after": "custom_width"},
		{
			"fieldname": "custom_length",
			"depends_on": "eval:!doc.custom_measurement_inputs || doc.custom_measurement_inputs.includes('custom_length')",
			"label": "Length",
			"fieldtype": "Float",
			"insert_after": "custom_insite_dim_cb",
		},
		{
			"fieldname": "custom_waste_factor",
			"depends_on": "eval:!doc.custom_measurement_inputs || doc.custom_measurement_inputs.includes('custom_waste_factor')",
			"label": "Wastage",
			"fieldtype": "Float",
			"insert_after": "custom_length",
			"description": "How much to add for waste. Type 1.1 to add 10 percent. Leave blank for none.",
		},
		{
			"fieldname": "custom_insite_calc_sb",
			"label": "Calculated",
			"fieldtype": "Section Break",
			"insert_after": "custom_waste_factor",
			"collapsible": 1,
		},
		{
			"fieldname": "custom_calculated_qty",
			"depends_on": "eval:doc.custom_calc_source",
			"label": "Calculated Quantity",
			"fieldtype": "Float",
			"insert_after": "custom_insite_calc_sb",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_calc_measure",
			"depends_on": "eval:doc.custom_calc_source",
			"label": "Rule Used",
			"fieldtype": "Data",
			"insert_after": "custom_calculated_qty",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_insite_calc_cb",
			"fieldtype": "Column Break",
			"insert_after": "custom_calc_measure",
		},
		{
			"fieldname": "custom_calc_source",
			"depends_on": "eval:doc.custom_calc_source",
			"label": "Work Item Type",
			"fieldtype": "Data",
			"insert_after": "custom_insite_calc_cb",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "custom_measurement_inputs",
			"label": "Measurement Inputs",
			"fieldtype": "Data",
			"insert_after": "custom_calc_dimensions",
			"read_only": 1,
			"hidden": 1,
			"no_copy": 1,
			"description": "Insite records which boxes this line's rule reads, so the rest stay out of the way.",
		},
		{
			"fieldname": "custom_calc_dimensions",
			"label": "Measurements Used",
			"fieldtype": "Small Text",
			"insert_after": "custom_calc_source",
			"read_only": 1,
			"hidden": 1,
			"no_copy": 1,
		},
	]


def _quality_inspection_fields():
	"""What ERPNext's Quality Inspection lacks for contracting, and nothing more.

	Rejected work is a Quality Inspection: it already holds the status, the
	inspector, the verifier, the remarks and the readings, and both Delivery
	Note Item and Sales Invoice Item link to one. Two things are missing. It
	does not know which scope of work it belongs to, and it has no quantity —
	`rejected_qty` exists only on Purchase Receipt Item, so on the selling side
	an inspection is pass or fail for a whole line with no way to say six of a
	hundred and sixty-eight.
	"""
	return [
		{
			"fieldname": "custom_insite_sb",
			"label": "Contracting",
			"fieldtype": "Section Break",
			"insert_after": "description",
		},
		{
			"fieldname": "scope_item",
			"label": "Scope",
			"fieldtype": "Link",
			"options": "Scope Item",
			"insert_after": "custom_insite_sb",
			"description": "Which scope of work this belongs to. Contract Progress reports rejected work against it.",
		},
		{
			"fieldname": "custom_insite_cb",
			"fieldtype": "Column Break",
			"insert_after": "scope_item",
		},
		{
			"fieldname": "custom_rejected_qty",
			"label": "Rejected Qty",
			"fieldtype": "Float",
			"insert_after": "custom_insite_cb",
			"depends_on": "eval:doc.status == 'Rejected'",
			"description": "How much of the line was refused. Leave blank if the whole line was.",
		},
		{
			"fieldname": "custom_rejected_amount",
			"label": "Rejected Amount",
			"fieldtype": "Currency",
			"insert_after": "custom_rejected_qty",
			"depends_on": "eval:doc.status == 'Rejected'",
			"read_only": 1,
			"description": "Worked out from the rate on the line this came off, in company currency.",
		},
	]


def get_custom_fields():
	fields = {doctype: _fields() for doctype in ITEM_DOCTYPES}
	fields["Quality Inspection"] = _quality_inspection_fields()
	return fields


def ensure_custom_fields():
	create_custom_fields(get_custom_fields(), ignore_validate=True)

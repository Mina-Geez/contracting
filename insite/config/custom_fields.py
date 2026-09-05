"""Code-defined Custom Fields for ERPNext item child tables (idempotent).

Applied through `create_custom_fields` in after_install / after_migrate — never
as fixtures, never through Export-Customizations. Fieldnames are stable and
owned by the app; only the labels are human-facing and translated.

The product vocabulary maps to these fieldnames as follows, and nowhere else:
`custom_base_qty` is **Count**, `custom_waste_factor` is **Wastage**.
"""

from __future__ import annotations

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from insite.calc.measures import PRESET_CHOICES
from insite.constants import ITEM_DOCTYPES, MEASURED_DOCTYPES


def _fields():
	return [
		{
			"fieldname": "custom_insite_dim_sb",
			"label": "Measurements",
			"fieldtype": "Section Break",
			"insert_after": "uom",
			"collapsible": 1,
			# Folded away on an ordinary line, open on a measured one. On a line
			# whose quantity comes from these boxes they are the only thing to
			# fill in, and hiding them behind a click — under a Quantity the
			# server is about to overwrite — had it exactly backwards.
			"collapsible_depends_on": "eval:doc.custom_measurement_inputs",
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
			# no_copy is set to 0 explicitly, not merely omitted: the field was
			# shipped no_copy, and create_custom_fields only writes the properties
			# it is given, so an already-installed site keeps the old value unless
			# the new one is stated. The measurement stamp must travel with the
			# line — ordering a quote (or reopening a draft) carries "measured by
			# rule X = this quantity", which is what lets the engine tell a line
			# already measured under an earlier rule from a blank one, and keep
			# the recorded quantity when the rule has since changed.
			"no_copy": 0,
		},
		{
			"fieldname": "custom_calc_measure",
			"depends_on": "eval:doc.custom_calc_source",
			"label": "Rule Used",
			"fieldtype": "Data",
			"insert_after": "custom_calculated_qty",
			"read_only": 1,
			"no_copy": 0,  # travels with the line — see custom_calculated_qty
		},
		{
			"fieldname": "custom_insite_calc_cb",
			"fieldtype": "Column Break",
			"insert_after": "custom_calc_measure",
		},
		{
			"fieldname": "custom_calc_source",
			"depends_on": "eval:doc.custom_calc_source",
			"label": "Measured By",
			"fieldtype": "Data",
			"insert_after": "custom_insite_calc_cb",
			"read_only": 1,
			"no_copy": 0,  # travels with the line — see custom_calculated_qty
		},
		{
			"fieldname": "custom_measurement_inputs",
			"label": "Measurement Inputs",
			"fieldtype": "Data",
			"insert_after": "custom_calc_source",
			"read_only": 1,
			"hidden": 1,
			"no_copy": 0,  # travels with the line — see custom_calculated_qty
			"description": "Insite records which boxes this line's rule reads, so the rest stay out of the way.",
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


def _quotation_project_field():
	"""An optional Project on the quotation header, which ERPNext does not give it.

	A Sales Order has one and a Quotation does not, so a contractor quoting more
	work on a job they are already running had nowhere to say which job. It also
	left the Scope picker with nothing to narrow by, offering every scope on the
	site.

	Optional on purpose, and the Scope on the line is optional too: at quote
	time the job may not exist yet. Nothing is enforced until the Sales Order.
	The fieldname matches the Sales Order's, so `get_mapped_doc` carries it
	across when the quote is ordered.
	"""
	return [
		{
			"fieldname": "project",
			"label": "Project",
			"fieldtype": "Link",
			"options": "Project",
			"insert_after": "order_type",
			"description": "Optional. Set it to narrow the Scope list on the lines, and it carries to the Sales Order.",
		}
	]


def _quotation_scope_field():
	"""The Scope on a Quotation line, which ERPNext will never add.

	`scope_item` reaches every other item table as an Accounting Dimension, but
	ERPNext only puts dimensions on doctypes that post to the ledger, and a
	Quotation does not. Quotation Item has no dimension section at all — no
	cost_center, no project.

	That broke the journey the app is built around. A quote could not carry a
	scope, Frappe silently dropped the value, and `get_mapped_doc` then handed
	the Sales Order a line with no scope — which Insite's own check refused. The
	fieldname must stay exactly `scope_item` so the mapping carries it across.
	"""
	return [
		{
			"fieldname": "scope_item",
			"label": "Scope",
			"fieldtype": "Link",
			"options": "Scope Item",
			"insert_after": "warehouse",
			"in_list_view": 1,
			"columns": 2,
			"description": "The scope of work this line belongs to. It carries through to the Sales Order.",
		}
	]


#: The record a rule can be written from, and where its Measurement section goes.
MEASURABLE_AFTER = {"Item Group": "item_group_name", "Item": "item_group", "Brand": "description"}


def _measurable_fields(insert_after):
	"""Say on the record itself whether it is measured, and how.

	A Measurement Rule stays its own record — that is what lets one rule cover a
	group, a brand, a template or an item, and what gives the ladder something
	to order. But nobody setting up an item group should have to know that. Tick
	**Measurable**, pick how, save: Insite writes the rule.

	These two are the input. The rule is the authority, so the summary is read
	back from it, and a rule edited directly puts these straight on next load.
	"""
	return [
		{
			"fieldname": "custom_insite_measurement_sb",
			"label": "Measurement",
			"fieldtype": "Section Break",
			"insert_after": insert_after,
			"collapsible": 1,
			"collapsible_depends_on": "custom_measurable",
		},
		{
			"fieldname": "custom_measurable",
			"label": "Measurable",
			"fieldtype": "Check",
			"insert_after": "custom_insite_measurement_sb",
			"description": "Tick when the quantity is worked out from measurements rather than typed.",
		},
		{
			"fieldname": "custom_measurement_preset",
			"label": "How is it measured?",
			"fieldtype": "Select",
			"options": "\n" + "\n".join(PRESET_CHOICES),
			"insert_after": "custom_measurable",
			"depends_on": "custom_measurable",
			"mandatory_depends_on": "custom_measurable",
			"description": "Pick the one that matches how you price this work.",
		},
		{
			"fieldname": "custom_measurement_summary",
			"label": "Worked out as",
			"fieldtype": "Data",
			"insert_after": "custom_measurement_preset",
			"depends_on": "custom_measurable",
			"read_only": 1,
			"allow_on_submit": 1,
			"description": "Open the rule to change the inputs, add a formula of your own, or write further numbers onto the line.",
		},
	]


def _show_in_grid(field_list, fieldnames):
	"""Bring a few boxes out of the row expander and into the grid itself."""
	for field in field_list:
		if field["fieldname"] in fieldnames:
			field["in_list_view"] = 1
			field["columns"] = 1


def get_custom_fields():
	fields = {doctype: _fields() for doctype in ITEM_DOCTYPES}
	# On the selling side the quantity is measured, so Count, Height and Width
	# belong in the grid where they are read and typed — forty lines should not
	# be forty expansions. On the buying side the same boxes exist but are
	# unused, so they stay tucked away and the grid stays uncluttered.
	for parent in MEASURED_DOCTYPES:
		_show_in_grid(fields[f"{parent} Item"], {"custom_base_qty", "custom_height", "custom_width"})
	fields["Quotation Item"] = fields["Quotation Item"] + _quotation_scope_field()
	fields["Quotation"] = _quotation_project_field()
	fields["Quality Inspection"] = _quality_inspection_fields()

	# Where a rule can be set from the record it measures. The field it sits
	# after differs because these three forms are laid out differently.
	for doctype, after in MEASURABLE_AFTER.items():
		fields[doctype] = _measurable_fields(after)
	return fields


def ensure_custom_fields():
	create_custom_fields(get_custom_fields(), ignore_validate=True)

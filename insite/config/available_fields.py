"""Which fields a Measurement Rule may read from a transaction line.

The list is Insite's own measurement fields, plus any other number field the
site has added to its sales lines. ERPNext's built-in numbers — rate, amount,
discounts, stock levels — are deliberately left out: they are results, not
measurements, and offering them would invite circular rules.
"""

from __future__ import annotations

import frappe

from insite.constants import ITEM_DOCTYPES

#: The line the field list is read from. Insite applies the same fields to every
#: item table, so one is representative.
REFERENCE_DOCTYPE = ITEM_DOCTYPES[1]  # Sales Order Item

NUMERIC_FIELDTYPES = ("Float", "Int", "Currency", "Percent")

#: Insite's own inputs, in the order a person thinks of them.
INSITE_FIELDS = (
	"custom_base_qty",
	"custom_height",
	"custom_width",
	"custom_length",
	"custom_waste_factor",
)

#: Insite writes these; reading them back into a formula would be circular.
_EXCLUDED = {"custom_calculated_qty"}


def measurable_fields(doctype: str | None = None) -> dict[str, str]:
	"""{fieldname: label} a rule may use, Insite's own fields first."""
	meta = frappe.get_meta(doctype or REFERENCE_DOCTYPE)
	found = {}

	for fieldname in INSITE_FIELDS:
		df = meta.get_field(fieldname)
		if df:
			found[fieldname] = _label_of(df)

	for df in meta.fields:
		if df.fieldtype not in NUMERIC_FIELDTYPES:
			continue
		if not df.fieldname.startswith("custom_"):
			continue
		if df.fieldname in _EXCLUDED or df.fieldname in found:
			continue
		found[df.fieldname] = _label_of(df)

	return found


def field_label(fieldname: str, doctype: str | None = None) -> str:
	"""The label a person sees for `fieldname`, falling back to the name itself."""
	return measurable_fields(doctype).get(fieldname, fieldname)


def _label_of(df) -> str:
	return df.label or df.fieldname

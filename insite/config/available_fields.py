"""Which fields a Measurement Rule may read.

A rule reads three kinds of number:

* **Line** — what someone measured on site: height, width, a panel count.
* **Item** — what is true of the material itself: the sheet it is cut from,
  its standard thickness. This belongs on the Item, not retyped on every line.
* **Constant** — a number the rule itself carries, such as a cutting allowance.

Only Insite's own fields and the ones a site added are offered. ERPNext's
built-in numbers — rate, amount, discounts, stock levels — are deliberately
left out: they are results, not measurements, and a rule that read them would
be circular.
"""

from __future__ import annotations

import frappe

from insite.constants import ITEM_DOCTYPES

#: Insite applies the same fields to every item table, so one is representative.
REFERENCE_DOCTYPE = ITEM_DOCTYPES[1]  # Sales Order Item

ITEM_DOCTYPE = "Item"

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
	"""{fieldname: label} a rule may read off a transaction line."""
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


def measurable_item_fields() -> dict[str, str]:
	"""{fieldname: label} a rule may read off the Item itself."""
	meta = frappe.get_meta(ITEM_DOCTYPE)
	return {
		df.fieldname: _label_of(df)
		for df in meta.fields
		if df.fieldtype in NUMERIC_FIELDTYPES and df.fieldname.startswith("custom_")
	}


def field_label(fieldname: str, doctype: str | None = None) -> str:
	"""The label a person sees for `fieldname`, falling back to the name itself."""
	return measurable_fields(doctype).get(fieldname, fieldname)


def _label_of(df) -> str:
	return df.label or df.fieldname

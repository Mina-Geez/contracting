"""Create the 'Scope Item' Accounting Dimension (fieldname `scope_item`).

ERPNext creates the dimension's fields in a background job, which is no good
during install: the verification would run before the job, and on a bench with
no worker the fields would never appear at all. A site in that state looks
installed but refuses every Sales Order — the engine marks lines as
contracting, then the Scope check demands a field that is not on the form.

So the fields are created synchronously here and then verified, and a failure
raises rather than whispering into the Error Log. An install that cannot finish
must say so.
"""

from __future__ import annotations

import frappe
from frappe import _

DIMENSION_DOCTYPE = "Scope Item"
DIMENSION_FIELDNAME = "scope_item"
DIMENSION_LABEL = "Scope"

#: The tables the app itself reads the dimension from.
_VERIFY_TABLES = (
	"Sales Order Item",
	"Delivery Note Item",
	"Sales Invoice Item",
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
)


def ensure_scope_dimension():
	doc = _get_or_create_dimension()
	_create_dimension_fields(doc)
	_verify_columns()


def _get_or_create_dimension():
	if frappe.db.exists("Accounting Dimension", DIMENSION_DOCTYPE):
		return frappe.get_doc("Accounting Dimension", DIMENSION_DOCTYPE)
	doc = frappe.new_doc("Accounting Dimension")
	doc.document_type = DIMENSION_DOCTYPE
	doc.label = DIMENSION_LABEL
	doc.fieldname = DIMENSION_FIELDNAME
	doc.insert(ignore_permissions=True)
	return doc


def _create_dimension_fields(doc):
	"""Run ERPNext's field creation now instead of waiting for a worker."""
	try:
		from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
			make_dimension_in_accounting_doctypes,
		)
	except ImportError:  # pragma: no cover - ERPNext is a required app
		return
	make_dimension_in_accounting_doctypes(doc=doc)


def _verify_columns():
	missing = [table for table in _VERIFY_TABLES if not _has_column(table)]
	if missing:
		frappe.throw(
			_(
				"Insite could not add the Scope field to: {0}. Run 'bench migrate' again; "
				"if it keeps failing, re-save the Scope Item Accounting Dimension."
			).format(", ".join(missing)),
			title=_("Scope Dimension Incomplete"),
		)


def _has_column(table):
	try:
		return DIMENSION_FIELDNAME in frappe.db.get_table_columns(table)
	except Exception:
		return False

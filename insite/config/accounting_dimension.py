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

from insite.constants import ITEM_DOCTYPES, QUALITY_INSPECTION

DIMENSION_DOCTYPE = "Scope Item"
DIMENSION_FIELDNAME = "scope_item"
DIMENSION_LABEL = "Scope"

#: The tables the app itself reads the dimension from.
#:
#: **Quotation Item is deliberately absent.** ERPNext only puts dimensions on
#: doctypes that post to the ledger, and a Quotation does not, so it will never
#: appear there however many times this runs. Insite adds `scope_item` to
#: Quotation Item as a plain custom field instead — see
#: `insite/config/custom_fields.py::_quotation_scope_field`.
_VERIFY_TABLES = (
	"Sales Order Item",
	"Delivery Note Item",
	"Sales Invoice Item",
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
)


#: Everywhere a Scope can be stored, and so everywhere it gets filtered by.
#: Derived rather than listed: a hand-kept copy of this drifted the moment it
#: was written, and missed two of the nine line tables.
#:
#: Neither ERPNext's dimension machinery nor Insite's own custom fields index
#: the column, and Contract Progress reads it with `scope_item in (...)` on
#: every run — a full scan of a table that grows a row per line of every
#: document a contractor ever raises.
_INDEXED_TABLES = (*ITEM_DOCTYPES, QUALITY_INSPECTION)


def ensure_scope_dimension():
	doc = _get_or_create_dimension()
	_create_dimension_fields(doc)
	_verify_columns()
	_index_scope_columns()


def _index_scope_columns():
	"""Index the Scope column wherever the app filters by it.

	An index is code: applied here on install and every migrate, so it cannot
	be lost to a database restore or forgotten on a new site. `add_index` is
	idempotent, so re-running costs nothing.

	Best effort per table — a site that does not have one of these (no Buying
	module, say) must not fail the whole migrate over an index.
	"""
	for doctype in _INDEXED_TABLES:
		if not _has_column(doctype):
			continue
		try:
			frappe.db.add_index(doctype, [DIMENSION_FIELDNAME])
		except Exception:
			frappe.log_error(
				title=f"Insite: could not index {DIMENSION_FIELDNAME} on {doctype}",
				message=frappe.get_traceback(),
			)


def _get_or_create_dimension():
	# ERPNext names the record after the dimension's label, not the doctype it
	# points at, so "Scope Item" is filed under "Scope". Look it up by what it
	# actually points at — searching by name would miss it and try to add a
	# second dimension for the same doctype, which ERPNext refuses.
	existing = frappe.db.get_value("Accounting Dimension", {"document_type": DIMENSION_DOCTYPE}, "name")
	if existing:
		return frappe.get_doc("Accounting Dimension", existing)
	doc = frappe.new_doc("Accounting Dimension")
	doc.document_type = DIMENSION_DOCTYPE
	doc.label = DIMENSION_LABEL
	doc.fieldname = DIMENSION_FIELDNAME
	doc.insert(ignore_permissions=True)
	return doc


def _create_dimension_fields(doc):
	"""Run ERPNext's field creation now instead of waiting for a worker.

	Best effort: ERPNext may have moved this helper, or a queued worker may
	already be doing the same work. Either way `_verify_columns` has the last
	word, so a failure here is logged rather than raised.
	"""
	try:
		from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
			make_dimension_in_accounting_doctypes,
		)

		make_dimension_in_accounting_doctypes(doc=doc)
	except Exception:
		frappe.log_error(
			title="Insite: could not create the Scope dimension fields directly",
			message=frappe.get_traceback(),
		)


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

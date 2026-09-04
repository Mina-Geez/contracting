"""Collecting a payment for one job.

A contractor is paid per project. When a payment arrives, the invoices to settle
it against are that job's invoices, and picking them out of every open invoice
for the customer is how money gets allocated to the wrong contract.

ERPNext's outstanding search filters on the **Payment Ledger Entry**, and that
is the limit of what it can do here. The ledger row behind an invoice is the
receivable posting — one row, against Debtors, carrying the document's
header-level dimensions. So:

**Project** is on that row, copied from the invoice header, and ERPNext could
have filtered on it. It does not: it builds its dimension conditions from
`get_dimensions()`, which returns custom dimensions only and leaves Project out.
ERPNext's own form says so — "project excluded in setup_dimension_filters" — so
a project handed to the search is read by nothing and silently dropped.

**Scope** is not on that row at all. It is `None`, because a scope belongs to a
line of work and the receivable posting is not a line. Worse than ignored: the
Scope *is* an active accounting dimension, because Insite registers it, so
ERPNext's search dutifully filters the ledger on `scope_item = <the scope>` and
matches nothing at all. That is also what puts a Scope filter in the Filters
dialog — a filter that always came back empty and so reported that a customer
owed nothing on a scope they owe plenty on. Insite put it there, so Insite makes
it mean something.

So both filters are taken out of the arguments before ERPNext's search runs —
the scope because leaving it in returns nothing, the project because nothing
reads it — and applied here afterwards. A project is matched on the document, a
scope on its lines, since that is where each one lives. With neither filter this
is a pass-through and the result is ERPNext's, untouched.
"""

from __future__ import annotations

import frappe
from erpnext.accounts.doctype.payment_entry.payment_entry import (
	get_outstanding_reference_documents as erpnext_outstanding,
)

from insite.config.accounting_dimension import DIMENSION_FIELDNAME as SCOPE_FIELD
from insite.constants import ITEM_DOCTYPES


@frappe.whitelist()
def get_outstanding_reference_documents(args, validate=False):
	"""ERPNext's outstanding invoices and orders, narrowed to a job."""
	args = dict(frappe.parse_json(args) if isinstance(args, str) else (args or {}))
	# Taken out before the search, not after. Left in, the scope makes ERPNext
	# filter the payment ledger on a column that is never set on a receivable
	# row, and the answer is always nothing.
	project = args.pop("project", None)
	scope = args.pop(SCOPE_FIELD, None)

	rows = erpnext_outstanding(args, validate=validate)
	if not rows:
		return rows

	keep = None
	if project:
		keep = _narrow(rows, _on_project, project)
	if scope:
		by_scope = _narrow(rows, _has_a_line_on, scope)
		keep = by_scope if keep is None else keep & by_scope

	if keep is None:
		return rows
	return [row for row in rows if row.get("voucher_no") in keep]


def _narrow(rows, belongs_to, value):
	"""The voucher names, among those already found, that `belongs_to` accepts.

	Grouped by voucher type so this costs one query per type rather than one per
	voucher: a customer with a hundred open invoices should not cost a hundred
	round trips.
	"""
	by_type = {}
	for row in rows:
		if row.get("voucher_type") and row.get("voucher_no"):
			by_type.setdefault(row["voucher_type"], set()).add(row["voucher_no"])

	found = set()
	for doctype, names in by_type.items():
		found.update(belongs_to(doctype, sorted(names), value))
	return found


def _on_project(doctype, names, project):
	"""Matched on the document, where ERPNext keeps the project."""
	if not frappe.db.has_column(doctype, "project"):
		return set()
	return set(
		frappe.get_all(
			doctype,
			filters={"name": ["in", names], "project": project},
			pluck="name",
			limit_page_length=0,
		)
	)


def _has_a_line_on(doctype, names, scope):
	"""Matched on the lines, where a scope lives.

	A voucher with no scope-bearing lines — a Journal Entry, say — keeps none of
	its rows. It cannot be shown to belong to the scope, and the filter is the
	user saying they only want the scope.
	"""
	child = f"{doctype} Item"
	if child not in ITEM_DOCTYPES:
		return set()
	return set(
		frappe.get_all(
			child,
			filters={"parent": ["in", names], SCOPE_FIELD: scope},
			pluck="parent",
			limit_page_length=0,
		)
	)

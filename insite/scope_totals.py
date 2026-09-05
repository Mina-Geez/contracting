"""The money against a scope, totalled one way for every report that needs it.

Contract Progress and Scope Profitability both ask what has been ordered against
a scope. If each worked it out its own way the two would eventually disagree,
and a reader has no way to tell which one is lying. So the totals live here once.

Everything comes back in company currency, **net**: `base_net_amount` on a line,
and the ledger's own debit and credit. A scope's figures are single numbers and
the documents behind them may be raised in any currency.

Net, not gross, because the ledger is net and these figures are read beside it.
`base_amount` is the line before any document-level discount and inclusive of a
tax charged that way, so a scope invoiced for 100,000 less a 10,000 discount
posted 90,000 to Sales and reported 100,000 as Invoiced. Worse in Scope
Profitability, which compared a tax-inclusive contract value against
tax-exclusive costs and overstated the margin by the whole of the VAT.

Every function takes an explicit list of scopes. The caller is expected to have
read that list with `get_list`, so the reader only ever sees scopes their
permissions allow. It also keeps these queries bounded: without the list they
would scan every line ever written.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from insite.config.accounting_dimension import DIMENSION_FIELDNAME as SCOPE_FIELD

#: An order in one of these states is no longer live: a Purchase Order in it is
#: not money we are going to spend, and a Sales Order in it is not work we are
#: going to do. Both sides read the same list — one of them used to ignore it.
SETTLED_ORDER_STATES = ("Closed",)

#: The two sides of the ledger a scope's profit is made of.
INCOME = "Income"
EXPENSE = "Expense"


def narrow_to_customer(conditions, customer):
	"""Add "this customer's jobs" to a set of filters on Project or on a scope.

	One definition for all three reports. A customer does not appear on a Scope
	Item — it appears on the Project — so filtering by customer means filtering
	to their projects. Doing that in one place is what stops two reports
	answering the same question differently.

	Read with `get_list`, so a reader still only sees the projects they may see.
	A customer with no projects narrows to nothing rather than to everything,
	which is the answer they asked for.
	"""
	if not customer:
		return conditions

	theirs = frappe.get_list("Project", filters={"customer": customer}, pluck="name", limit_page_length=0)
	wanted = conditions.get("project")
	if wanted and not isinstance(wanted, list | tuple):
		# Both a customer and one project: the project has to be one of theirs.
		theirs = [name for name in theirs if name == wanted]

	conditions["project"] = ["in", theirs]
	return conditions


def sum_lines_by_scope(child_doctype, parent_doctype, scopes, company=None, skip_states=()):
	"""Submitted net line amounts per scope, in company currency."""
	if not scopes:
		return {}

	_require_scope_field(child_doctype)

	child = frappe.qb.DocType(child_doctype)
	parent = frappe.qb.DocType(parent_doctype)
	scope_column = getattr(child, SCOPE_FIELD)

	query = (
		frappe.qb.from_(child)
		.join(parent)
		.on(child.parent == parent.name)
		.select(scope_column.as_("scope"), Sum(child.base_net_amount).as_("amount"))
		.where(scope_column.isin(scopes))
		.where(parent.docstatus == 1)
		.groupby(scope_column)
	)
	if company:
		query = query.where(parent.company == company)
	if skip_states:
		query = query.where(parent.status.notin(skip_states))

	return {row.scope: flt(row.amount) for row in query.run(as_dict=True)}


def posted_by_scope(scopes, company=None):
	"""Income and expense actually posted against each scope.

	Read from the ledger rather than from invoice lines, so that a credit note,
	a journal entry or an expense claim carrying the scope counts too. This is
	the same source ERPNext's own Profitability Analysis reads, which is what
	lets the two agree.

	Returns `{scope: {"income": x, "expense": y}}`, both as positive numbers.
	"""
	if not scopes:
		return {}

	ledger = frappe.qb.DocType("GL Entry")
	account = frappe.qb.DocType("Account")

	query = (
		frappe.qb.from_(ledger)
		.join(account)
		.on(ledger.account == account.name)
		.select(
			getattr(ledger, SCOPE_FIELD).as_("scope"),
			account.root_type,
			Sum(ledger.debit).as_("debit"),
			Sum(ledger.credit).as_("credit"),
		)
		.where(getattr(ledger, SCOPE_FIELD).isin(scopes))
		.where(ledger.is_cancelled == 0)
		.where(account.root_type.isin([INCOME, EXPENSE]))
		.groupby(getattr(ledger, SCOPE_FIELD), account.root_type)
	)
	if company:
		query = query.where(ledger.company == company)

	totals = {}
	for row in query.run(as_dict=True):
		side = totals.setdefault(row.scope, {"income": 0.0, "expense": 0.0})
		# Income is earned as a credit, expense is incurred as a debit. Taking
		# the difference nets off the reversals rather than double counting them.
		if row.root_type == INCOME:
			side["income"] += flt(row.credit) - flt(row.debit)
		else:
			side["expense"] += flt(row.debit) - flt(row.credit)
	return totals


def committed_by_scope(scopes, company=None):
	"""Ordered from suppliers against each scope and not yet invoiced.

	The number no financial report holds. A Purchase Order is a promise to pay
	that has not reached the ledger, so a scope can look profitable right up to
	the moment the invoices arrive.

	**Worked out by comparing the two totals, not from `billed_amt`.** ERPNext
	only maintains `billed_amt` on a Purchase Order line when the invoice is
	raised *from* the order, through `po_detail`. An invoice keyed in from the
	supplier's paperwork instead — the everyday case in an accounts office —
	posts its cost to the ledger while leaving the order looking unbilled. The
	same spend was then counted twice: once as Cost, once as Committed. Ten
	thousand spent read as sixteen thousand expected.

	So: everything ordered for the scope, less everything invoiced for it,
	floored at zero. Invoicing more than was ordered is not a negative
	commitment — the excess is posted, and Cost already has it.
	"""
	if not scopes:
		return {}

	ordered = sum_lines_by_scope(
		"Purchase Order Item", "Purchase Order", scopes, company, skip_states=SETTLED_ORDER_STATES
	)
	invoiced = sum_lines_by_scope("Purchase Invoice Item", "Purchase Invoice", scopes, company)

	return {scope: max(0.0, flt(ordered.get(scope)) - flt(invoiced.get(scope))) for scope in ordered}


def _require_scope_field(doctype):
	"""A missing scope column means migrate has not finished, not that there is no data."""
	if SCOPE_FIELD in _columns_of(doctype):
		return
	frappe.throw(
		_("The Scope field is missing from {0}. Run 'bench migrate' to finish setting up Insite.").format(
			_(doctype)
		),
		title=_("Setup Incomplete"),
	)


def _columns_of(doctype):
	try:
		return frappe.db.get_table_columns(doctype)
	except Exception:
		return []

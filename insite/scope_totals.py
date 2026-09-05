"""The money against a scope, totalled one way for every report that needs it.

Contract Progress and Scope Profitability both ask what has been ordered against
a scope. If each worked it out its own way the two would eventually disagree,
and a reader has no way to tell which one is lying. So the totals live here once.

Everything comes back in company currency — `base_amount` on a line, the
ledger's own debit and credit, a purchase line converted at its order's rate.
A scope's figures are single numbers and the documents behind them may be raised
in any currency.

Every function takes an explicit list of scopes. The caller is expected to have
read that list with `get_list`, so the reader only ever sees scopes their
permissions allow. It also keeps these queries bounded: without the list they
would scan every line ever written.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.query_builder import Case
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from insite.config.accounting_dimension import DIMENSION_FIELDNAME as SCOPE_FIELD

#: A Purchase Order in one of these states is no longer money we are going to spend.
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


def sum_lines_by_scope(child_doctype, parent_doctype, scopes, company=None):
	"""Submitted line amounts per scope, in company currency."""
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
		.select(scope_column.as_("scope"), Sum(child.base_amount).as_("amount"))
		.where(scope_column.isin(scopes))
		.where(parent.docstatus == 1)
		.groupby(scope_column)
	)
	if company:
		query = query.where(parent.company == company)

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
	the moment the invoices arrive. `billed_amt` is what the supplier has already
	invoiced, so the rest is still to come.

	A line billed for more than it was ordered contributes nothing rather than a
	negative, because an over-billed line is not a negative commitment — the
	excess is already posted and counted as cost.
	"""
	if not scopes:
		return {}

	_require_scope_field("Purchase Order Item")

	line = frappe.qb.DocType("Purchase Order Item")
	order = frappe.qb.DocType("Purchase Order")
	scope_column = getattr(line, SCOPE_FIELD)
	outstanding = (
		Case()
		.when(line.amount > line.billed_amt, (line.amount - line.billed_amt) * order.conversion_rate)
		.else_(0)
	)

	query = (
		frappe.qb.from_(line)
		.join(order)
		.on(line.parent == order.name)
		.select(scope_column.as_("scope"), Sum(outstanding).as_("amount"))
		.where(scope_column.isin(scopes))
		.where(order.docstatus == 1)
		.where(order.status.notin(SETTLED_ORDER_STATES))
		.groupby(scope_column)
	)
	if company:
		query = query.where(order.company == company)

	return {row.scope: flt(row.amount) for row in query.run(as_dict=True)}


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

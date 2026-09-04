"""Scope Profitability — what a scope is worth, what it has cost, and what is still coming.

ERPNext already answers the ledger question. Register `Scope Item` as an
accounting dimension, which Insite does, and **Profitability Analysis** reports
income, expense and gross profit per scope, **Budget Variance Report** compares a
scope against a budget, and the P&L can be filtered to one scope. None of that
needed building and none of it is repeated here.

What none of them can see is the commitment. A Purchase Order is a promise to
pay that has not reached the ledger, so a scope reads as profitable right up to
the moment the invoices land. That is the classic way a contract is lost quietly:
the margin was spent months before anyone posted it.

So this report puts the ledger beside the order book:

    Contract Value   submitted Sales Orders — what the job is worth, variations included
    Revenue          posted to income accounts
    Cost             posted to expense accounts
    Committed        ordered from suppliers, not yet invoiced
    Expected Cost    Cost + Committed — what the scope will have cost
    Margin           Contract Value - Expected Cost
    Margin %         Margin over Contract Value

Two deliberate differences from the ERPNext reports:

**No date range.** A contract is not a fiscal year. Costing a scope over a period
while its contract value covers the whole job would compare two different things,
so every figure here is life-to-date.

**Worst first.** The rows are ordered by margin ascending. A report you open to
control a job should open on the job that needs controlling.

Scopes are read with `get_list`, so a reader only sees what their permissions
allow, and the money is totalled for those scopes alone.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from insite.scope_totals import committed_by_scope, posted_by_scope, sum_lines_by_scope


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Scope"),
			"fieldname": "scope",
			"fieldtype": "Link",
			"options": "Scope Item",
			"width": 200,
		},
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 160,
		},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{
			"label": _("Contract Value"),
			"fieldname": "contract_value",
			"fieldtype": "Currency",
			"width": 130,
		},
		{"label": _("Revenue"), "fieldname": "revenue", "fieldtype": "Currency", "width": 120},
		{"label": _("Cost"), "fieldname": "cost", "fieldtype": "Currency", "width": 120},
		{"label": _("Committed"), "fieldname": "committed", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Expected Cost"),
			"fieldname": "expected_cost",
			"fieldtype": "Currency",
			"width": 130,
		},
		{"label": _("Margin"), "fieldname": "margin", "fieldtype": "Currency", "width": 120},
		{"label": _("Margin %"), "fieldname": "margin_pct", "fieldtype": "Percent", "width": 100},
	]


def get_data(filters):
	scopes = _scopes(filters)
	if not scopes:
		return []

	names = [scope.name for scope in scopes]
	company = filters.get("company")
	ordered = sum_lines_by_scope("Sales Order Item", "Sales Order", names, company)
	posted = posted_by_scope(names, company)
	committed = committed_by_scope(names, company)

	data = []
	for scope in scopes:
		ledger = posted.get(scope.name) or {}
		contract_value = flt(ordered.get(scope.name))
		cost = flt(ledger.get("expense"))
		still_to_come = flt(committed.get(scope.name))
		expected_cost = cost + still_to_come
		margin = contract_value - expected_cost
		data.append(
			{
				"scope": scope.name,
				"project": scope.project,
				"status": scope.status,
				"contract_value": contract_value,
				"revenue": flt(ledger.get("income")),
				"cost": cost,
				"committed": still_to_come,
				"expected_cost": expected_cost,
				"margin": margin,
				"margin_pct": (margin / contract_value * 100.0) if contract_value else 0.0,
			}
		)

	data.sort(key=lambda row: row["margin"])
	return data


def _scopes(filters):
	"""Scopes the reader is allowed to see, narrowed by the report filters."""
	conditions = {}
	for field in ("status", "project", "company"):
		if filters.get(field):
			conditions[field] = filters.get(field)
	return frappe.get_list(
		"Scope Item",
		filters=conditions,
		fields=["name", "project", "status"],
		order_by="name asc",
		limit_page_length=0,
	)

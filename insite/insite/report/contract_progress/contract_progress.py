"""Contract Progress — planned against ordered, delivered and invoiced, per scope.

Variations are raised as further Sales Orders against the same scope, so the
ordered total is the current committed value of the work and **Variance to
Plan** (ordered minus planned) is what a variation looks like in this report.
The planned amount stays the agreed baseline until someone updates it.

Scopes are read with `get_list` so the reader only ever sees the scopes their
permissions allow, and the money is then totalled for those scopes alone. That
keeps the report both correct and bounded: without the scope list the three
aggregates would scan every sales line ever written.

Amounts are summed in company currency (`base_amount`), because a scope's
planned figure is a single number and documents may be raised in any currency.

**Rejected** sits beside Delivered so the delivered figure cannot read better
than the site does. It is the value of submitted Quality Inspections still
marked Rejected against the scope — a claim, not a ledger entry.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from insite.constants import QI_REJECTED, QUALITY_INSPECTION
from insite.scope_totals import SETTLED_ORDER_STATES, narrow_to_customer, sum_lines_by_scope


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
			"width": 220,
		},
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 160,
		},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Planned"), "fieldname": "planned", "fieldtype": "Currency", "width": 120},
		{"label": _("Ordered"), "fieldname": "ordered", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Variance to Plan"),
			"fieldname": "variance_to_plan",
			"fieldtype": "Currency",
			"width": 130,
		},
		{"label": _("Delivered"), "fieldname": "delivered", "fieldtype": "Currency", "width": 120},
		{"label": _("Rejected"), "fieldname": "rejected_open", "fieldtype": "Currency", "width": 120},
		{"label": _("Invoiced"), "fieldname": "invoiced", "fieldtype": "Currency", "width": 120},
		{"label": _("Left to Invoice"), "fieldname": "variance", "fieldtype": "Currency", "width": 130},
		{"label": _("% Invoiced"), "fieldname": "pct_invoiced", "fieldtype": "Percent", "width": 100},
	]


def get_data(filters):
	scopes = _scopes(filters)
	if not scopes:
		return []

	names = [scope.name for scope in scopes]
	# A Sales Order closed because the work was abandoned is not ordered work.
	# The purchase side already skipped Closed; this side did not, so the two
	# halves of one file disagreed about what the word meant.
	ordered = sum_lines_by_scope(
		"Sales Order Item", "Sales Order", names, filters.get("company"), skip_states=SETTLED_ORDER_STATES
	)
	delivered = sum_lines_by_scope("Delivery Note Item", "Delivery Note", names, filters.get("company"))
	invoiced = sum_lines_by_scope("Sales Invoice Item", "Sales Invoice", names, filters.get("company"))
	rejected = _open_rejections(names, filters.get("company"))

	data = []
	for scope in scopes:
		planned = flt(scope.planned_amount)
		ordered_amount = flt(ordered.get(scope.name))
		invoiced_amount = flt(invoiced.get(scope.name))
		# What is committed today: the orders raised, or the plan if none yet.
		committed = ordered_amount or planned
		data.append(
			{
				"scope": scope.name,
				"scope_title": scope.scope_title,
				"project": scope.project,
				"status": scope.status,
				"planned": planned,
				"ordered": ordered_amount,
				"variance_to_plan": ordered_amount - planned,
				"delivered": flt(delivered.get(scope.name)),
				"rejected_open": flt(rejected.get(scope.name)),
				"invoiced": invoiced_amount,
				"variance": committed - invoiced_amount,
				"pct_invoiced": (invoiced_amount / committed * 100.0) if committed else 0.0,
			}
		)

	if data:
		data.append(_total_row(data))
	return data


def _total_row(rows):
	"""One totals line, with the percentage worked out from the totals.

	Frappe's own total row averaged the Percent column — 42.84%, 0, 0 came out
	as 14.28% — which is not what "% Invoiced overall" means. So the report turns
	that off (add_total_row is 0) and totals its own money, then divides the
	summed invoiced by the summed commitment. The JS marks the row with is_total
	so the grid can show it in bold and label it "Total".
	"""
	fields = ("planned", "ordered", "variance_to_plan", "delivered", "rejected_open", "invoiced", "variance")
	total = {field: sum(flt(row[field]) for row in rows) for field in fields}
	# Committed per row is "ordered, or the plan if nothing is ordered yet", so
	# the overall commitment is the sum of those, not ordered-or-planned of the
	# totals. Left to Invoice already carries it: committed = invoiced + variance.
	committed = total["invoiced"] + total["variance"]
	total["pct_invoiced"] = (total["invoiced"] / committed * 100.0) if committed else 0.0
	total["scope"] = ""
	total["is_total"] = 1
	return total


def _scopes(filters):
	"""Scopes the reader is allowed to see, narrowed by the report filters."""
	conditions = {}
	for field in ("status", "project", "company"):
		if filters.get(field):
			conditions[field] = filters.get(field)
	narrow_to_customer(conditions, filters.get("customer"))
	return frappe.get_list(
		"Scope Item",
		filters=conditions,
		fields=["name", "scope_title", "project", "status", "planned_amount"],
		order_by="name asc",
		limit_page_length=0,
	)


def _open_rejections(scopes, company=None):
	"""Value of the work still failing inspection, per scope.

	Rejected work is a submitted Quality Inspection still marked Rejected —
	ERPNext's own document, to which Insite adds only a Scope and a quantity.

	A management figure, not a ledger one: it is a claim against work already
	delivered, and nothing has been credited yet. That is why it sits beside
	Delivered rather than being netted off it, and why Left to Invoice is
	untouched — work that gets redone is still owed to you.

	Built with the query builder rather than `get_all`: Frappe refuses an
	aggregate written as a field string ("SQL functions are not allowed as
	strings in SELECT"), and that refusal would take the whole report down, not
	just this column.
	"""
	inspection = frappe.qb.DocType(QUALITY_INSPECTION)
	query = (
		frappe.qb.from_(inspection)
		.select(inspection.scope_item, Sum(inspection.custom_rejected_amount).as_("amount"))
		.where(inspection.scope_item.isin(scopes))
		.where(inspection.status == QI_REJECTED)
		.where(inspection.docstatus == 1)
	)
	if company:
		query = query.where(inspection.company == company)

	rows = query.groupby(inspection.scope_item).run(as_dict=True)
	return {row.scope_item: flt(row.amount) for row in rows}

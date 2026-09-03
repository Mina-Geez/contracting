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

**Rejected (Open)** sits beside Delivered so the delivered figure cannot read
better than the site does. It is the value of Rejections still open against the
scope — a claim, not a ledger entry.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from insite.config.accounting_dimension import DIMENSION_FIELDNAME as SCOPE_FIELD
from insite.constants import REJECTION_OPEN


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
		{
			"label": _("Rejected (Open)"),
			"fieldname": "rejected_open",
			"fieldtype": "Currency",
			"width": 130,
		},
		{"label": _("Invoiced"), "fieldname": "invoiced", "fieldtype": "Currency", "width": 120},
		{"label": _("Left to Invoice"), "fieldname": "variance", "fieldtype": "Currency", "width": 130},
		{"label": _("% Invoiced"), "fieldname": "pct_invoiced", "fieldtype": "Percent", "width": 100},
	]


def get_data(filters):
	scopes = _scopes(filters)
	if not scopes:
		return []

	names = [scope.name for scope in scopes]
	ordered = _sum_by_scope("Sales Order Item", "Sales Order", names, filters.get("company"))
	delivered = _sum_by_scope("Delivery Note Item", "Delivery Note", names, filters.get("company"))
	invoiced = _sum_by_scope("Sales Invoice Item", "Sales Invoice", names, filters.get("company"))
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
		fields=["name", "scope_title", "status", "planned_amount"],
		order_by="name asc",
		limit_page_length=0,
	)


def _open_rejections(scopes, company=None):
	"""Value of the rejections still open, per scope.

	A management figure, not a ledger one: an open rejection is a claim against
	work already delivered, and nothing has been credited yet. That is why it
	sits beside Delivered rather than being netted off it, and why Left to
	Invoice is untouched — reworked work is still owed to you.
	"""
	conditions = {"scope_item": ["in", scopes], "status": REJECTION_OPEN}
	if company:
		conditions["company"] = company
	rows = frappe.get_all(
		"Rejection",
		filters=conditions,
		fields=["scope_item as scope", "sum(rejected_amount) as amount"],
		group_by="scope_item",
	)
	return {row.scope: flt(row.amount) for row in rows}


def _sum_by_scope(child_doctype, parent_doctype, scopes, company=None):
	"""Total submitted line amounts per scope, in company currency."""
	if SCOPE_FIELD not in _columns_of(child_doctype):
		frappe.throw(
			_("The Scope field is missing from {0}. Run 'bench migrate' to finish setting up Insite.").format(
				_(child_doctype)
			),
			title=_("Setup Incomplete"),
		)

	conditions = ["parent.docstatus = 1", f"child.`{SCOPE_FIELD}` in %(scopes)s"]
	values = {"scopes": scopes}
	if company:
		conditions.append("parent.company = %(company)s")
		values["company"] = company

	rows = frappe.db.sql(
		f"""
		select child.`{SCOPE_FIELD}` as scope, sum(child.base_amount) as amount
		from `tab{child_doctype}` child
		join `tab{parent_doctype}` parent on child.parent = parent.name
		where {" and ".join(conditions)}
		group by child.`{SCOPE_FIELD}`
		""",
		values,
		as_dict=True,
	)
	return {row.scope: flt(row.amount) for row in rows}


def _columns_of(doctype):
	try:
		return frappe.db.get_table_columns(doctype)
	except Exception:
		return []

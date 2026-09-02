"""Clause Portfolio — planned vs executed (delivered) vs invoiced per scope.

Aggregates transaction amounts by the 'Contract Clause' accounting dimension
(fieldname ``contract_clause``) so each scope-of-work clause shows its planned
value against delivered and invoiced reality.
"""

import frappe
from frappe import _
from frappe.utils import flt

from contracting.config.accounting_dimension import DIMENSION_FIELDNAME as FIELD


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Clause"), "fieldname": "clause", "fieldtype": "Link", "options": "Contract Clause", "width": 180},
		{"label": _("Title"), "fieldname": "title", "fieldtype": "Data", "width": 200},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Planned"), "fieldname": "planned", "fieldtype": "Currency", "width": 120},
		{"label": _("Delivered"), "fieldname": "delivered", "fieldtype": "Currency", "width": 120},
		{"label": _("Invoiced"), "fieldname": "invoiced", "fieldtype": "Currency", "width": 120},
		{"label": _("Variance (Planned − Invoiced)"), "fieldname": "variance", "fieldtype": "Currency", "width": 160},
		{"label": _("% Invoiced"), "fieldname": "pct_invoiced", "fieldtype": "Percent", "width": 100},
	]


def _sum_by_clause(child_dt, parent_dt, company=None):
	conditions = ["p.docstatus = 1", f"c.`{FIELD}` is not null", f"c.`{FIELD}` != ''"]
	params = {}
	if company:
		conditions.append("p.company = %(company)s")
		params["company"] = company
	try:
		rows = frappe.db.sql(
			f"""
			select c.`{FIELD}` as clause, sum(c.amount) as amt
			from `tab{child_dt}` c
			join `tab{parent_dt}` p on c.parent = p.name
			where {" and ".join(conditions)}
			group by c.`{FIELD}`
			""",
			params,
			as_dict=True,
		)
		return {r.clause: flt(r.amt) for r in rows}
	except Exception:  # noqa: BLE001 - dimension column may be absent on this table
		return {}


def get_data(filters):
	clause_filters = {}
	if filters.get("status"):
		clause_filters["status"] = filters.status

	clauses = frappe.get_all(
		"Contract Clause",
		filters=clause_filters,
		fields=["name", "clause_title", "status", "planned_amount"],
		order_by="name asc",
	)

	delivered = _sum_by_clause("Delivery Note Item", "Delivery Note", filters.get("company"))
	invoiced = _sum_by_clause("Sales Invoice Item", "Sales Invoice", filters.get("company"))

	data = []
	for c in clauses:
		planned = flt(c.planned_amount)
		inv = flt(invoiced.get(c.name))
		data.append(
			{
				"clause": c.name,
				"title": c.clause_title,
				"status": c.status,
				"planned": planned,
				"delivered": flt(delivered.get(c.name)),
				"invoiced": inv,
				"variance": planned - inv,
				"pct_invoiced": (inv / planned * 100.0) if planned else 0.0,
			}
		)
	return data

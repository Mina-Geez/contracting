"""Contract Progress — planned/ordered/delivered/invoiced per Scope Item."""
import frappe
from frappe import _
from frappe.utils import flt

FIELD = "scope_item"


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("Scope"), "fieldname": "scope", "fieldtype": "Link", "options": "Scope Item", "width": 140},
        {"label": _("Title"), "fieldname": "title", "fieldtype": "Data", "width": 200},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 80},
        {"label": _("Planned"), "fieldname": "planned", "fieldtype": "Currency", "width": 110},
        {"label": _("Net Variations"), "fieldname": "net_variations", "fieldtype": "Currency", "width": 110},
        {"label": _("Revised"), "fieldname": "revised", "fieldtype": "Currency", "width": 110},
        {"label": _("Ordered"), "fieldname": "ordered", "fieldtype": "Currency", "width": 110},
        {"label": _("Delivered"), "fieldname": "delivered", "fieldtype": "Currency", "width": 110},
        {"label": _("Invoiced"), "fieldname": "invoiced", "fieldtype": "Currency", "width": 110},
        {"label": _("Variance (Revised − Invoiced)"), "fieldname": "variance", "fieldtype": "Currency", "width": 150},
        {"label": _("% Invoiced"), "fieldname": "pct_invoiced", "fieldtype": "Percent", "width": 90},
        {"label": _("Over-run"), "fieldname": "overrun", "fieldtype": "Data", "width": 80},
    ]


def _sum_by_scope(child_dt, parent_dt, company=None):
    conditions = ["p.docstatus = 1", f"c.`{FIELD}` is not null", f"c.`{FIELD}` != ''"]
    params = {}
    if company:
        conditions.append("p.company = %(company)s")
        params["company"] = company
    try:
        rows = frappe.db.sql(
            f"""select c.`{FIELD}` as scope, sum(c.amount) as amt
                from `tab{child_dt}` c join `tab{parent_dt}` p on c.parent = p.name
                where {' and '.join(conditions)} group by c.`{FIELD}`""",
            params, as_dict=True)
        return {r.scope: flt(r.amt) for r in rows}
    except Exception:  # noqa: BLE001
        return {}


def get_data(filters):
    scope_filters = {}
    if filters.get("status"):
        scope_filters["status"] = filters.status
    if filters.get("project"):
        scope_filters["project"] = filters.project
    scopes = frappe.get_all("Scope Item", filters=scope_filters,
                            fields=["name", "scope_title", "status", "original_planned_amount",
                                    "net_variations_amount", "revised_planned_amount"],
                            order_by="name asc")
    ordered = _sum_by_scope("Sales Order Item", "Sales Order", filters.get("company"))
    delivered = _sum_by_scope("Delivery Note Item", "Delivery Note", filters.get("company"))
    invoiced = _sum_by_scope("Sales Invoice Item", "Sales Invoice", filters.get("company"))
    data = []
    for s in scopes:
        revised = flt(s.revised_planned_amount) or flt(s.original_planned_amount)
        o, d, i = flt(ordered.get(s.name)), flt(delivered.get(s.name)), flt(invoiced.get(s.name))
        data.append({
            "scope": s.name, "title": s.scope_title, "status": s.status,
            "planned": flt(s.original_planned_amount), "net_variations": flt(s.net_variations_amount),
            "revised": revised, "ordered": o, "delivered": d, "invoiced": i,
            "variance": revised - i,
            "pct_invoiced": (i / revised * 100.0) if revised else 0.0,
            "overrun": _("Yes") if max(o, d, i) > revised and revised else "",
        })
    return data

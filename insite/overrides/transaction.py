"""doc_events for sales/purchase transactions.

Two responsibilities, both server-authoritative:

1. `recalculate` — compute measured quantities before ERPNext totals the doc.
   Sell-side only: purchases carry the Scope tag for cost attribution, but their
   quantities are what the buyer actually ordered, not a derived measurement.
2. `enforce_project_scope` — keep contracting work traceable by requiring a
   Project and a Scope. It applies ONLY to lines the measurement engine matched
   (a Work Item Type rule), so ordinary non-contracting sales on the same site
   are unaffected, and it can be switched off in Contracting Settings.
"""
from __future__ import annotations

import frappe
from frappe import _

from insite.calc import engine

#: Documents whose quantities are derived from measurements.
_MEASURED = {"Quotation", "Sales Order", "Delivery Note", "Sales Invoice"}

#: Documents that must carry Project + Scope (Quotation stays free: early stage).
_ENFORCED = {"Sales Order", "Delivery Note", "Sales Invoice"}


def recalculate(doc, method=None):
    """before_validate: recompute measured line quantities (sell cycle only)."""
    if doc.doctype not in _MEASURED:
        return
    try:
        engine.recalculate_document(doc)
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(title="Insite: measurement engine error", message=frappe.get_traceback())
        raise


def enforce_project_scope(doc, method=None):
    """validate: require Project + Scope on contracting lines.

    A line counts as contracting when the engine matched a Work Item Type rule
    to it in `before_validate` (which stamps `custom_calc_source`). Documents
    with no contracting lines are left alone.
    """
    if doc.doctype not in _ENFORCED:
        return
    if not frappe.db.get_single_value("Contracting Settings", "enforce_project_and_scope"):
        return

    contracting_rows = [row for row in (doc.get("items") or []) if row.get("custom_calc_source")]
    if not contracting_rows:
        return

    if not doc.get("project"):
        frappe.throw(
            _("Add a Project before saving this {0}. Contracting work is tracked per project.").format(_(doc.doctype)),
            title=_("Project Required"),
        )

    missing = [str(row.idx) for row in contracting_rows if not row.get("scope_item")]
    if missing:
        frappe.throw(
            _("Choose a Scope on row(s): {0}. Contracting lines are tracked per scope of work.").format(", ".join(missing)),
            title=_("Scope Required"),
        )

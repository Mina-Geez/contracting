"""doc_events for sales/purchase transactions."""
from __future__ import annotations
import frappe
from frappe import _
from insite.calc import engine

_SELL = {"Quotation", "Sales Order", "Delivery Note", "Sales Invoice"}
_ENFORCE = {"Sales Order", "Delivery Note", "Sales Invoice"}  # not Quotation (early stage)


def recalculate(doc, method=None):
    try:
        engine.recalculate_document(doc)
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(title="Insite: calc engine error", message=frappe.get_traceback())
        raise


def enforce_project_scope(doc, method=None):
    """A Sales Order (and downstream) needs a Project + a Scope on every line."""
    if doc.doctype not in _ENFORCE:
        return
    if not doc.get("project"):
        frappe.throw(_("Add a Project before saving this {0}.").format(_(doc.doctype)))
    for row in (doc.get("items") or []):
        if not row.get("scope_item"):
            frappe.throw(_("Row {0}: choose a Scope.").format(row.idx))

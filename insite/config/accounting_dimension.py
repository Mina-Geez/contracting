"""Create the 'Scope Item' Accounting Dimension (fieldname `scope_item`).

Guards ERPNext issue #25485 (partial dimension-field creation) by verifying the
`scope_item` column exists on the core sales/purchase item tables after create.
"""
from __future__ import annotations
import frappe

DIMENSION_DOCTYPE = "Scope Item"
DIMENSION_FIELDNAME = "scope_item"
DIMENSION_LABEL = "Scope"

_VERIFY_TABLES = ["Sales Order Item", "Delivery Note Item", "Sales Invoice Item",
                  "Purchase Order Item", "Purchase Receipt Item", "Purchase Invoice Item"]


def ensure_scope_dimension():
    if not frappe.db.exists("Accounting Dimension", DIMENSION_DOCTYPE):
        doc = frappe.new_doc("Accounting Dimension")
        doc.document_type = DIMENSION_DOCTYPE
        doc.label = DIMENSION_LABEL
        doc.fieldname = DIMENSION_FIELDNAME
        doc.insert(ignore_permissions=True)
    _verify_columns()


def _verify_columns():
    missing = []
    for dt in _VERIFY_TABLES:
        try:
            cols = frappe.db.get_table_columns(dt)
        except Exception:  # noqa: BLE001
            cols = []
        if DIMENSION_FIELDNAME not in cols:
            missing.append(dt)
    if missing:
        frappe.log_error(
            title="Insite: scope_item dimension missing columns",
            message="Missing on: " + ", ".join(missing) +
                    " — re-run migrate or re-save the Accounting Dimension.",
        )

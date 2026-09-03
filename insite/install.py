"""Idempotent install/migrate setup for Insite. No db_set; documented APIs only."""
from __future__ import annotations
import frappe
from insite.config.custom_fields import ensure_custom_fields
from insite.config.accounting_dimension import ensure_scope_dimension

ROLES = [
    ("Contracting Manager", "Full access to Work Item Types, Scopes, and Variation Orders."),
]


def after_install():
    _setup()


def after_migrate():
    _setup()


def _setup():
    create_roles()
    ensure_custom_fields()
    ensure_settings_singleton()
    ensure_scope_dimension()
    try:
        from insite.config.price_visibility import apply_from_settings
        apply_from_settings()
    except Exception:  # noqa: BLE001
        frappe.log_error(title="Insite: price visibility setup skipped", message=frappe.get_traceback())


def create_roles():
    for role_name, desc in ROLES:
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name,
                            "desk_access": 1, "description": desc}).insert(ignore_permissions=True)


def ensure_settings_singleton():
    if not frappe.db.exists("Contracting Settings", "Contracting Settings"):
        frappe.get_single("Contracting Settings").save(ignore_permissions=True)

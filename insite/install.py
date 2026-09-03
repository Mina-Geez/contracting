"""Idempotent install and migrate setup for Insite.

Safe to re-run: every step either checks first or upserts. No `db_set`, no
fixtures of standard doctypes — documented APIs only.
"""

from __future__ import annotations

import frappe

from insite.config.accounting_dimension import ensure_scope_dimension
from insite.config.custom_fields import ensure_custom_fields
from insite.config.price_visibility import apply_from_settings

ROLES = [
	("Contracting Manager", "Sets up Work Item Types, and manages scopes and variation orders."),
]


def after_install():
	setup()


def after_migrate():
	setup()


def setup():
	"""Everything the app needs on a site. Runs on install and every migrate."""
	create_roles()
	ensure_custom_fields()
	ensure_settings_singleton()
	ensure_scope_dimension()
	apply_from_settings()


def create_roles():
	for role_name, description in ROLES:
		if frappe.db.exists("Role", role_name):
			# Frappe auto-creates roles named in a DocType's permissions, so the
			# role usually exists already but without our description.
			role = frappe.get_doc("Role", role_name)
			if not role.description:
				role.description = description
				role.save(ignore_permissions=True)
			continue
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": 1,
				"description": description,
			}
		).insert(ignore_permissions=True)


def ensure_settings_singleton():
	"""Create the single, and seed a default a Single will not backfill.

	A new field on an existing Single keeps a NULL value on sites that already
	have the document — the JSON `default` only applies to a fresh one. Left
	alone, enforcement would read as "off" after an upgrade.
	"""
	settings = frappe.get_single("Contracting Settings")
	if frappe.db.get_single_value("Contracting Settings", "enforce_project_and_scope") is None:
		settings.enforce_project_and_scope = 1
		settings.save(ignore_permissions=True)
	elif not frappe.db.exists("Singles", {"doctype": "Contracting Settings"}):
		settings.save(ignore_permissions=True)

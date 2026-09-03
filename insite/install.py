"""Idempotent install and migrate setup for Insite.

Safe to re-run: every step either checks first or upserts. No `db_set`, no
fixtures of standard doctypes — documented APIs only.
"""

from __future__ import annotations

import frappe

from insite.config.accounting_dimension import ensure_scope_dimension
from insite.config.custom_fields import ensure_custom_fields
from insite.insite.doctype.measurement_field.measurement_field import apply_all as apply_site_fields

#: Roles Insite needs. Frappe's Role doctype carries no description field, so
#: what each role is for lives in docs/SETUP.md, not on the record.
ROLE_NAMES = ("Contracting Manager",)


def after_install():
	setup()


def after_migrate():
	setup()


def setup():
	"""Everything the app needs on a site. Runs on install and every migrate."""
	create_roles()
	ensure_custom_fields()
	apply_site_fields()  # after Insite's own: these are inserted after them
	ensure_settings_singleton()
	ensure_scope_dimension()


def create_roles():
	"""Create the roles Insite needs, if a DocType's permissions have not already.

	Frappe creates any role named in a permissions block while it syncs the
	doctypes, so on a normal install there is usually nothing left to do here.
	"""
	for role_name in ROLE_NAMES:
		if frappe.db.exists("Role", role_name):
			continue
		frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 1}).insert(
			ignore_permissions=True
		)


def ensure_settings_singleton():
	"""Create the single, and seed a default a Single will not backfill.

	A new field on an existing Single keeps a NULL value on sites that already
	have the document — the JSON `default` only applies to a fresh one. Left
	alone, enforcement would read as "off" after an upgrade.
	"""
	settings = frappe.get_single("Insite Settings")
	if frappe.db.get_single_value("Insite Settings", "enforce_project_and_scope") is None:
		settings.enforce_project_and_scope = 1
	# Saving unconditionally also materialises the document on a fresh site.
	settings.save(ignore_permissions=True)

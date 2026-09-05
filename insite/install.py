"""Idempotent install and migrate setup for Insite.

Safe to re-run: every step either checks first or upserts. No `db_set`, no
fixtures of standard doctypes — documented APIs only.
"""

from __future__ import annotations

import frappe

from insite.config.accounting_dimension import ensure_scope_dimension
from insite.config.custom_fields import ensure_custom_fields
from insite.insite.doctype.measurement_field.measurement_field import apply_all as apply_site_fields
from insite.insite.doctype.measurement_field.measurement_field import ensure_standard_fields

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
	# The shipped boxes are recorded in the master after the fields themselves
	# exist, so the list shows every measurable number in one place — the way
	# UOM ships its own and a site adds more.
	ensure_standard_fields()
	apply_site_fields()  # after Insite's own: these are inserted after them
	ensure_settings_singleton()
	allow_an_item_on_more_than_one_line()
	ensure_scope_dimension()


def allow_an_item_on_more_than_one_line():
	"""Let the same item appear on several lines, under several scopes.

	One item belongs to many scopes at once: a door handle belongs to every
	scope that has doors, at a different rate and a different quantity in each.
	Insite's whole model is a scope per line, so a document has to be able to
	carry the same item more than once.

	ERPNext refuses that by default — "Item entered multiple times" — and the
	switch is in Selling Settings, off. A contracting site cannot work without
	it, so Insite turns it on, once, the way it creates its roles and fields.
	It is never turned back off: a site that has deliberately cleared it has
	said something, and this runs on every migrate.
	"""
	if frappe.db.get_single_value("Selling Settings", "allow_multiple_items"):
		return
	settings = frappe.get_single("Selling Settings")
	settings.allow_multiple_items = 1
	settings.save(ignore_permissions=True)


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

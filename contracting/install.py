"""Idempotent install / migrate setup for the contracting app.

Everything here is safe to re-run: seeding uses create-if-missing, custom fields
and the accounting dimension are applied via idempotent helpers, and roles/single
settings are created only when absent. No ``db_set`` / raw writes; documented APIs
only.
"""

from __future__ import annotations

import frappe

from contracting.calc.methods import STANDARD_METHODS
from contracting.config.accounting_dimension import ensure_contract_clause_dimension
from contracting.config.custom_fields import ensure_custom_fields

CONTRACTING_ROLES = [
	("Contracting Manager", "Full access to Trade Profiles, Calculation Rules, and Contract Clauses."),
	("Contracting Implementer", "May author the privileged 'formula' calculation escape hatch."),
]


def after_install():
	_setup()


def after_migrate():
	# Kept lightweight and idempotent; runs on every `bench migrate`.
	_setup()


def _setup():
	create_roles()
	seed_calculation_methods()
	ensure_custom_fields()
	ensure_settings_singleton()
	ensure_contract_clause_dimension()
	# Price visibility is re-asserted from the saved setting (no-op if disabled).
	try:
		from contracting.config.price_visibility import apply_from_settings

		apply_from_settings()
	except Exception:  # noqa: BLE001
		frappe.log_error(
			title="Contracting: price visibility setup skipped",
			message=frappe.get_traceback(),
		)


def create_roles():
	for role_name, desc in CONTRACTING_ROLES:
		if not frappe.db.exists("Role", role_name):
			frappe.get_doc(
				{
					"doctype": "Role",
					"role_name": role_name,
					"desk_access": 1,
					"description": desc,
				}
			).insert(ignore_permissions=True)


def seed_calculation_methods():
	"""Seed the fixed method registry (create-only; never clobbers user edits)."""
	for method in STANDARD_METHODS:
		if frappe.db.exists("Calculation Method", method["method_key"]):
			continue
		doc = frappe.get_doc({"doctype": "Calculation Method", "enabled": 1, **method})
		doc.insert(ignore_permissions=True)


def ensure_settings_singleton():
	if not frappe.db.exists("Contracting Settings", "Contracting Settings"):
		# Single DocType: touching it materializes defaults.
		frappe.get_single("Contracting Settings").save(ignore_permissions=True)

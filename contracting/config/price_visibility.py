"""Role-based price visibility (optional, OFF by default, fully reversible).

When enabled in Contracting Settings, price/amount fields on selling line items
are raised to permlevel 1 (via Property Setters), and only the configured roles
are granted permlevel-1 access on the parent documents. Disabling reverts both.

Nothing is applied at install time — only when a user turns the setting on and
saves Contracting Settings — so a fresh site is never surprised by hidden prices.
"""

from __future__ import annotations

import frappe

# child item table -> price fields to protect
SELLING_PRICE_FIELDS = {
	"Quotation Item": ["rate", "amount", "price_list_rate", "base_rate", "base_amount"],
	"Sales Order Item": ["rate", "amount", "price_list_rate", "base_rate", "base_amount"],
	"Delivery Note Item": ["rate", "amount", "price_list_rate", "base_rate", "base_amount"],
	"Sales Invoice Item": ["rate", "amount", "price_list_rate", "base_rate", "base_amount"],
}

# child item table -> its parent transaction (where permlevel-1 perms live)
PARENT_OF = {
	"Quotation Item": "Quotation",
	"Sales Order Item": "Sales Order",
	"Delivery Note Item": "Delivery Note",
	"Sales Invoice Item": "Sales Invoice",
}

PERMLEVEL = 1


def apply_from_settings() -> dict:
	"""Read Contracting Settings and apply the current visibility configuration."""
	settings = frappe.get_single("Contracting Settings")
	enable = bool(getattr(settings, "enable_price_visibility", 0))
	roles = [r.role for r in (settings.get("price_visibility_roles") or []) if r.role]
	return apply(enable, roles)


def apply(enable: bool, roles: list[str]) -> dict:
	"""Apply (enable) or revert (disable) price visibility. Returns a summary."""
	if enable and not roles:
		frappe.log_error(
			title="Contracting: price visibility not applied",
			message="Enable requested with no roles configured; refusing to hide "
			"prices from everyone. Add at least one role in Contracting Settings.",
		)
		return {"applied": False, "reason": "no roles configured"}

	changed = []
	for child_dt, fields in SELLING_PRICE_FIELDS.items():
		for fieldname in fields:
			_set_field_permlevel(child_dt, fieldname, PERMLEVEL if enable else 0)
			changed.append(f"{child_dt}.{fieldname}")
		frappe.clear_cache(doctype=child_dt)

	for parent_dt in set(PARENT_OF.values()):
		if enable:
			_grant_permlevel(parent_dt, roles)
		else:
			_revoke_permlevel(parent_dt)
		frappe.clear_cache(doctype=parent_dt)

	return {"applied": True, "enabled": enable, "roles": roles, "fields": changed}


def _set_field_permlevel(doctype: str, fieldname: str, permlevel: int) -> None:
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	if permlevel:
		make_property_setter(
			doctype,
			fieldname,
			"permlevel",
			str(permlevel),
			"Int",
			for_doctype=False,
			validate_fields_for_doctype=False,
		)
	else:
		ps_name = f"{doctype}-{fieldname}-permlevel"
		if frappe.db.exists("Property Setter", ps_name):
			frappe.delete_doc("Property Setter", ps_name, ignore_permissions=True)


def _grant_permlevel(parent_dt: str, roles: list[str]) -> None:
	from frappe.permissions import add_permission, update_permission_property

	for role in roles:
		add_permission(parent_dt, role, PERMLEVEL)
		for ptype in ("read", "write"):
			update_permission_property(parent_dt, role, PERMLEVEL, ptype, 1, validate=False)


def _revoke_permlevel(parent_dt: str) -> None:
	# Remove every permlevel-1 permission row we may have added on this doctype.
	rows = frappe.get_all(
		"Custom DocPerm",
		filters={"parent": parent_dt, "permlevel": PERMLEVEL},
		pluck="name",
	)
	for name in rows:
		frappe.delete_doc("Custom DocPerm", name, ignore_permissions=True, force=True)

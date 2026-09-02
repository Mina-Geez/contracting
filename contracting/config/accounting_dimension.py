"""Create & verify the 'Contract Clause' Accounting Dimension in code.

Creating an Accounting Dimension makes ERPNext auto-inject a tagging custom field
across GL-affecting transaction doctypes (and their item child tables) via
``make_dimension_in_accounting_doctypes``, so a clause tag flows
Quotation → SO → Delivery/PO → SI/PI → GL, enabling per-scope reporting.

Two documented hazards are guarded here:
  * the field injection can be enqueued as a background job, so we force it
    synchronously; and
  * partial-creation bug (ERPNext #25485) where injection stops after N of M
    doctypes — so we VERIFY field counts post-creation and repair the gap.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint

DIMENSION_DOCUMENT_TYPE = "Contract Clause"
DIMENSION_FIELDNAME = "contract_clause"  # == frappe.scrub("Contract Clause")


def _erpnext_api():
	"""Return the ERPNext accounting_dimension helpers, or None if unavailable."""
	try:
		from erpnext.accounts.doctype.accounting_dimension import accounting_dimension as ad

		return ad
	except Exception:  # noqa: BLE001
		return None


def ensure_contract_clause_dimension() -> dict:
	"""Idempotently create the dimension and verify/repair its injected fields."""
	# The 'Contract Clause' *master* DocType is shipped by this app, so it already
	# exists after migrate. Guard anyway.
	if not frappe.db.exists("DocType", DIMENSION_DOCUMENT_TYPE):
		frappe.log_error(
			title="Contracting: Contract Clause DocType missing",
			message="Cannot create the Accounting Dimension before its master DocType exists.",
		)
		return {"created": False, "reason": "master doctype missing"}

	created = False
	if not frappe.db.exists("Accounting Dimension", {"document_type": DIMENSION_DOCUMENT_TYPE}):
		doc = frappe.get_doc(
			{
				"doctype": "Accounting Dimension",
				"document_type": DIMENSION_DOCUMENT_TYPE,
				"label": DIMENSION_DOCUMENT_TYPE,
				"fieldname": DIMENSION_FIELDNAME,
				"disabled": 0,
			}
		)
		doc.insert(ignore_permissions=True)
		created = True
	else:
		doc = frappe.get_doc("Accounting Dimension", {"document_type": DIMENSION_DOCUMENT_TYPE})

	# Force synchronous field injection (guards against the enqueue race).
	ad = _erpnext_api()
	if ad and hasattr(ad, "make_dimension_in_accounting_doctypes"):
		try:
			ad.make_dimension_in_accounting_doctypes(doc=doc)
		except Exception:  # noqa: BLE001
			frappe.log_error(
				title="Contracting: dimension field injection error",
				message=frappe.get_traceback(),
			)

	summary = verify_dimension_fields(repair=True)
	summary["created"] = created
	return summary


def _expected_doctypes(ad) -> list[str]:
	if ad and hasattr(ad, "get_doctypes_with_dimensions"):
		try:
			return list(ad.get_doctypes_with_dimensions())
		except Exception:  # noqa: BLE001
			pass
	return []


def verify_dimension_fields(repair: bool = False) -> dict:
	"""Check the dimension custom field exists on every expected doctype.

	Returns {fieldname, expected, present, missing:[...], repaired:[...]}. When
	``repair`` is set, attempts to create any missing field directly.
	"""
	ad = _erpnext_api()
	expected = _expected_doctypes(ad)
	missing, repaired = [], []

	for dt in expected:
		if not frappe.db.exists(
			"Custom Field", {"dt": dt, "fieldname": DIMENSION_FIELDNAME}
		):
			missing.append(dt)

	if repair and missing:
		from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

		for dt in list(missing):
			try:
				create_custom_fields(
					{
						dt: [
							{
								"fieldname": DIMENSION_FIELDNAME,
								"label": DIMENSION_DOCUMENT_TYPE,
								"fieldtype": "Link",
								"options": DIMENSION_DOCUMENT_TYPE,
								"insert_after": "cost_center"
								if frappe.get_meta(dt).has_field("cost_center")
								else None,
							}
						]
					},
					ignore_validate=True,
				)
				repaired.append(dt)
				missing.remove(dt)
			except Exception:  # noqa: BLE001
				frappe.log_error(
					title=f"Contracting: could not repair dimension field on {dt}",
					message=frappe.get_traceback(),
				)

	summary = {
		"fieldname": DIMENSION_FIELDNAME,
		"expected": len(expected),
		"present": len(expected) - len(missing),
		"missing": missing,
		"repaired": repaired,
	}
	if missing:
		frappe.log_error(
			title="Contracting: Contract Clause dimension partial creation",
			message=frappe.as_json(summary),
		)
	return summary

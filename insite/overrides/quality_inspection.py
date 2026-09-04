"""Quality Inspection — ERPNext's record of work that was refused.

Insite does not have a rejection document. ERPNext's Quality Inspection already
holds the status, who inspected it, who verified it, the remarks and the
readings, and both Delivery Note Item and Sales Invoice Item link to one. What
it does not know is which scope of work the inspection belongs to, and how much
of the line was refused — `rejected_qty` lives only on Purchase Receipt Item,
so on the selling side an inspection is pass or fail for a whole line.

This fills in those two, and nothing else. It never writes a status.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from insite.constants import QI_REJECTED, QI_SELL_SIDE_REFERENCES


def price_the_rejection(doc, method=None):
	"""validate: carry the scope down from the line, and value what was refused."""
	line = _source_line(doc)

	# The delivery already knows its scope. Asking for it twice invites the
	# two to disagree, and the report believes this one.
	if line and line.get("scope_item") and not doc.get("scope_item"):
		doc.scope_item = line.scope_item

	_check_scope_company(doc)

	if doc.status != QI_REJECTED:
		doc.custom_rejected_amount = 0
		return

	# Blank means the whole line was refused — the common case on site.
	quantity = flt(doc.get("custom_rejected_qty")) or (flt(line.qty) if line else 0)
	if line and quantity > flt(line.qty):
		frappe.throw(
			_("Only {0} of {1} was delivered on that line, so {2} cannot have been rejected.").format(
				flt(line.qty), doc.item_code, quantity
			),
			title=_("More Rejected Than Delivered"),
		)

	doc.custom_rejected_amount = quantity * flt(line.base_rate) if line else 0


def _source_line(doc):
	"""The sell-side line this inspection came off, if it came off one."""
	if doc.get("reference_type") not in QI_SELL_SIDE_REFERENCES or not doc.get("reference_name"):
		return None

	child_doctype = f"{doc.reference_type} Item"
	# `child_row_reference` names the exact row; without it fall back to the
	# item, which is right whenever an item appears once on the document.
	if doc.get("child_row_reference"):
		filters = {"name": doc.child_row_reference}
	else:
		filters = {"parent": doc.reference_name, "item_code": doc.item_code}

	return frappe.db.get_value(child_doctype, filters, ["qty", "base_rate", "scope_item"], as_dict=True)


def _check_scope_company(doc):
	"""A scope from another company would report the rejection against the wrong job."""
	if not doc.get("scope_item") or not doc.get("company"):
		return
	scope = frappe.db.get_value("Scope Item", doc.scope_item, ["company", "scope_title"], as_dict=True)
	if scope and scope.company and scope.company != doc.company:
		frappe.throw(
			_("The Scope '{0}' belongs to company {1}, but this inspection is for {2}.").format(
				scope.scope_title or doc.scope_item, scope.company, doc.company
			),
			title=_("Scope Belongs to Another Company"),
		)

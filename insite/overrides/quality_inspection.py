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

from insite.constants import QI_REJECTED, QI_SELL_SIDE_REFERENCES, QUALITY_INSPECTION


def price_the_rejection(doc, method=None):
	"""validate: carry the scope down from the line, and value what was refused."""
	line = _source_line(doc)

	# The delivery already knows its scope. Asking for it twice invites the
	# two to disagree, and the report believes this one.
	if line and line.get("scope_item") and not doc.get("scope_item"):
		doc.scope_item = line.scope_item

	_warn_if_another_line_could_have_been_meant(doc, line)
	_check_scope_company(doc)

	if doc.status != QI_REJECTED:
		doc.custom_rejected_amount = 0
		return

	# Blank means the whole line was refused — the common case on site.
	quantity = flt(doc.get("custom_rejected_qty")) or (flt(line.qty) if line else 0)
	if line:
		_refuse_more_than_was_delivered(doc, line, quantity)

	doc.custom_rejected_amount = quantity * flt(line.base_rate) if line else 0


def _refuse_more_than_was_delivered(doc, line, quantity):
	"""Cap the rejections on a line by what that line delivered — all of them, together.

	Each inspection used to be capped only against its own line quantity, and
	nothing looked at the others. Three inspections on the same delivery line,
	each rejecting the whole ten, totalled thirty rejected out of ten delivered,
	and Contract Progress added them all up. On a live job that column only ever
	grows.
	"""
	delivered = flt(line.qty)
	already = _rejected_elsewhere_on(line, except_inspection=doc.name)
	if quantity + already <= delivered:
		return

	if already:
		frappe.throw(
			_(
				"{0} of {1} was delivered on that line and {2} is already rejected, so {3} more cannot be."
			).format(delivered, doc.item_code, already, quantity),
			title=_("More Rejected Than Delivered"),
		)
	frappe.throw(
		_("Only {0} of {1} was delivered on that line, so {2} cannot have been rejected.").format(
			delivered, doc.item_code, quantity
		),
		title=_("More Rejected Than Delivered"),
	)


def _rejected_elsewhere_on(line, except_inspection=None):
	"""How much of this delivery line other submitted inspections already refuse."""
	filters = {
		"child_row_reference": line.name,
		"status": QI_REJECTED,
		"docstatus": 1,
	}
	if except_inspection:
		filters["name"] = ["!=", except_inspection]

	total = 0.0
	for row in frappe.get_all(
		QUALITY_INSPECTION, filters=filters, fields=["custom_rejected_qty"], limit_page_length=0
	):
		# Blank meant the whole line, there as here.
		total += flt(row.custom_rejected_qty) or flt(line.qty)
	return total


#: What the inspection needs from the line it came off.
_LINE_FIELDS = ["name", "idx", "qty", "base_rate", "scope_item"]


def _source_line(doc):
	"""The sell-side line this inspection came off, if it came off one.

	One item can appear on several lines of the same document under different
	scopes — a door handle belongs to every scope that has doors — and those
	lines carry different rates. So when the inspection does not name its row,
	matching by item code is a guess, and a wrong guess files the rejection
	against the wrong scope at the wrong money with nothing to show for it.
	Refuse instead.
	"""
	if doc.get("reference_type") not in QI_SELL_SIDE_REFERENCES or not doc.get("reference_name"):
		return None

	child_doctype = f"{doc.reference_type} Item"
	if doc.get("child_row_reference"):
		return frappe.db.get_value(
			child_doctype, {"name": doc.child_row_reference}, _LINE_FIELDS, as_dict=True
		)

	rows = frappe.get_all(
		child_doctype,
		filters={"parent": doc.reference_name, "item_code": doc.item_code},
		fields=_LINE_FIELDS,
		order_by="idx asc",
	)
	if not rows:
		return None
	if len(rows) > 1:
		frappe.throw(
			_(
				"{0} is on {1} lines of {2}, and they may be different scopes at "
				"different rates. Create the inspection from the line that failed, so "
				"Insite knows which one it was."
			).format(doc.item_code, len(rows), doc.reference_name),
			title=_("Which Line Failed?"),
		)
	return rows[0]


def _warn_if_another_line_could_have_been_meant(doc, line):
	"""Say so when the document has the same item under a different scope.

	One item belongs to several scopes at once — a door handle belongs to every
	scope that has doors — and those lines carry different rates. When an
	inspection does not come off a line, ERPNext binds it to the first row that
	matches the item code and says nothing. That silently files the rejection
	against one scope at that scope's rate when the other was meant, which is
	real money moving between scopes with nothing to show for it.

	Insite cannot tell a deliberate choice from ERPNext's default, so it does
	not override it. It just stops the ambiguity being silent.
	"""
	if not line or not doc.get("scope_item"):
		return

	others = frappe.get_all(
		f"{doc.reference_type} Item",
		filters={
			"parent": doc.reference_name,
			"item_code": doc.item_code,
			"name": ["!=", line.name],
			# No None in this list: SQL compares anything to NULL as NULL, so a
			# single None turns the whole NOT IN false and the query silently
			# matches nothing. Lines with no scope are excluded anyway — a blank
			# scope is not a different scope.
			"scope_item": ["not in", ["", doc.scope_item]],
		},
		fields=["idx", "scope_item"],
		order_by="idx asc",
	)
	if not others:
		return

	elsewhere = ", ".join(_("line {0} ({1})").format(row.idx, _scope_title(row.scope_item)) for row in others)
	frappe.msgprint(
		_(
			"This is filed against line {0}, {1}. The same item is also on {2}. "
			"Check it is the right line — the scopes are billed at different rates."
		).format(line.idx, _scope_title(doc.scope_item), elsewhere),
		title=_("Same Item on Another Scope"),
		indicator="orange",
	)


def _scope_title(scope):
	return frappe.db.get_value("Scope Item", scope, "scope_title") or scope


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

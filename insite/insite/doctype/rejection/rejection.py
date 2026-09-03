"""Rejection — delivered work the client would not accept.

A Rejection is a claim, not an accounting entry. Nothing here posts to a
ledger: the record says that some of what you delivered has to be redone,
credited or argued about, and it stays Open until one of those happens. That
is deliberate. ERPNext already knows how to move stock and money with a return
and a credit note, and a second set of books that drifts from the first would
be worse than no record at all. So Insite links the credit note you raised
rather than raising one, and its only real power is to speak up when someone
invoices a scope that still has rejected work on it.

The buying side is not here on purpose. A Purchase Receipt already carries a
rejected quantity and a rejected warehouse, and Insite's Scope field is on
those lines, so a supplier's bad batch already lands against the right scope.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today

from insite.constants import REJECTION_CREDITED, REJECTION_OPEN


class Rejection(Document):
	def validate(self):
		scope = self._scope()
		self.check_quantity()
		self.check_scope_matches(scope)
		self.set_amount()
		self.track_closing()
		self.set_summary(scope)

	def _scope(self):
		"""The scope this rejection is against, read once for the whole save."""
		if not self.scope_item:
			return None
		return frappe.db.get_value(
			"Scope Item", self.scope_item, ["project", "company", "scope_title"], as_dict=True
		)

	def check_quantity(self):
		if flt(self.rejected_qty) <= 0:
			frappe.throw(
				_("How much was rejected? Enter a quantity greater than zero."),
				title=_("Quantity Required"),
			)

	def check_scope_matches(self, scope):
		"""A scope from another project would report the rejection against the wrong job."""
		if not scope:
			return
		if scope.project and self.project and scope.project != self.project:
			frappe.throw(
				_("The Scope '{0}' belongs to project {1}, but this rejection is for {2}.").format(
					scope.scope_title or self.scope_item, scope.project, self.project
				),
				title=_("Scope Belongs to Another Project"),
			)
		if scope.company and self.company and scope.company != self.company:
			frappe.throw(
				_("The Scope '{0}' belongs to company {1}, but this rejection is for {2}.").format(
					scope.scope_title or self.scope_item, scope.company, self.company
				),
				title=_("Scope Belongs to Another Company"),
			)

	def set_amount(self):
		"""Value it from the rate when there is one, and leave it alone when there is not.

		Reporting a rejection should never be held up for want of a price, so a
		rejection with no rate is allowed — it simply carries whatever amount
		was typed, or none.
		"""
		if flt(self.rate):
			self.rejected_amount = flt(self.rejected_qty) * flt(self.rate)

	def track_closing(self):
		if self.status == REJECTION_OPEN:
			self.closed_on = None
			return
		if self.status == REJECTION_CREDITED and not self.credit_note:
			frappe.throw(
				_("Which credit note settled this? Insite records the one you raised."),
				title=_("Credit Note Required"),
			)
		self.closed_on = self.closed_on or today()

	def set_summary(self, scope):
		"""One line naming what was rejected. It is the record's title everywhere."""
		measure = f"{flt(self.rejected_qty):g}"
		if self.uom:
			measure = f"{measure} {self.uom}"
		what = self.item_name or self.item_code or _("work")
		title = scope.scope_title if scope else None
		self.rejection_summary = f"{measure} {what}" + (f" — {title}" if title else "")

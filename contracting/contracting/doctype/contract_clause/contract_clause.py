"""Contract Clause master — scope-of-work record + Accounting Dimension reference.

Guards (server-authoritative, upgrade-safe controller validation):
  * identity-lock: once a submitted transaction references a clause, its identity
    fields cannot be changed;
  * completion-gate: a clause can only be marked Completed once real (submitted)
    work references it, and cannot be Cancelled while still referenced.

NOTE: the exact locked-field set and completion semantics are a generic
reconstruction — the live glass site's original guard bodies were not available
this session (production was off-limits). Reconcile against AUDIT.md output on the
clone and adjust LOCKED_FIELDS / gate logic to match.
"""

import frappe
from frappe import _
from frappe.model.document import Document

from contracting.config.accounting_dimension import DIMENSION_FIELDNAME

# Identity fields frozen once the clause is referenced by submitted work.
LOCKED_FIELDS = ["project", "customer", "currency"]

# (child item table, parent transaction) pairs to scan for references.
_ITEM_REFERENCE_SOURCES = [
	("Sales Order Item", "Sales Order"),
	("Quotation Item", "Quotation"),
	("Delivery Note Item", "Delivery Note"),
	("Sales Invoice Item", "Sales Invoice"),
	("Purchase Order Item", "Purchase Order"),
	("Purchase Receipt Item", "Purchase Receipt"),
	("Purchase Invoice Item", "Purchase Invoice"),
]


class ContractClause(Document):
	def validate(self):
		self._enforce_identity_lock()
		self._enforce_completion_gate()

	# --- identity-lock -----------------------------------------------------
	def _enforce_identity_lock(self):
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		changed = [f for f in LOCKED_FIELDS if (before.get(f) or None) != (self.get(f) or None)]
		if changed and self.is_referenced_by_submitted():
			labels = ", ".join(_(self.meta.get_label(f)) for f in changed)
			frappe.throw(
				_(
					"This clause is referenced by submitted transactions; the following "
					"identity fields are locked and cannot be changed: {0}."
				).format(labels),
				title=_("Clause Locked"),
			)

	# --- completion-gate ---------------------------------------------------
	def _enforce_completion_gate(self):
		if self.status == "Completed" and not self.is_referenced_by_submitted():
			frappe.throw(
				_("Cannot mark a clause Completed before any submitted work references it."),
				title=_("Completion Blocked"),
			)
		if self.status == "Cancelled" and self.is_referenced_by_submitted():
			frappe.throw(
				_("Cannot cancel a clause that is referenced by submitted transactions."),
				title=_("Cancellation Blocked"),
			)

	# --- reference detection ----------------------------------------------
	def is_referenced_by_submitted(self) -> bool:
		"""True if any submitted transaction (or GL Entry) tags this clause."""
		# Financial postings first (covers parent-level dimension usage).
		try:
			if frappe.db.exists("GL Entry", {DIMENSION_FIELDNAME: self.name, "is_cancelled": 0}):
				return True
		except Exception:  # noqa: BLE001 - dimension may not exist on GL Entry yet
			pass

		for child_dt, parent_dt in _ITEM_REFERENCE_SOURCES:
			try:
				hit = frappe.db.sql(
					f"""
					select 1
					from `tab{child_dt}` c
					join `tab{parent_dt}` p on c.parent = p.name
					where c.`{DIMENSION_FIELDNAME}` = %s and p.docstatus = 1
					limit 1
					""",
					(self.name,),
				)
				if hit:
					return True
			except Exception:  # noqa: BLE001 - column may not exist on this table
				continue
		return False

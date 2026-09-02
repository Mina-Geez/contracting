import frappe
from frappe import _
from frappe.model.document import Document

from contracting.config.price_visibility import apply as apply_price_visibility


class ContractingSettings(Document):
	def on_update(self):
		"""Apply (or revert) role-based price visibility whenever settings change."""
		enable = bool(self.enable_price_visibility)
		roles = [r.role for r in (self.price_visibility_roles or []) if r.role]
		try:
			result = apply_price_visibility(enable, roles)
		except Exception:  # noqa: BLE001 - never hard-block saving the settings
			frappe.log_error(
				title="Contracting: price visibility apply failed",
				message=frappe.get_traceback(),
			)
			frappe.msgprint(
				_("Price visibility could not be applied — see the Error Log."),
				indicator="orange",
				alert=True,
			)
			return

		if not result.get("applied") and enable:
			frappe.msgprint(
				_("Add at least one role before enabling price visibility."),
				indicator="orange",
				alert=True,
			)

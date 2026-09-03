from __future__ import annotations

from frappe.model.document import Document


class ContractingSettings(Document):
	def on_update(self):
		from insite.config.price_visibility import apply_from_settings

		apply_from_settings()

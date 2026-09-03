"""Contracting Price Role — a role that may see prices.

No logic of its own. The controller still has to exist — Frappe imports a
module for every DocType, child tables included.
"""

from __future__ import annotations

from frappe.model.document import Document


class ContractingPriceRole(Document):
	pass

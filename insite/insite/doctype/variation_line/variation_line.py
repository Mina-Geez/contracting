"""Variation Line — one scope change inside a Variation Order.

No logic of its own: the parent Variation Order validates the rows and drives
the recompute of each affected Scope Item. The controller still has to exist —
Frappe imports a module for every DocType, child tables included.
"""
from __future__ import annotations

from frappe.model.document import Document


class VariationLine(Document):
	pass

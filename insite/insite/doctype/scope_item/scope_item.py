"""Scope Item — a scope of work inside a project.

The scope is one of Insite's two axes; the ERPNext Project is the other. It
carries no logic of its own: the planned amount is entered by the Contracting
Manager and version-tracked by Frappe, and everything actual is read from the
standard sales documents that carry this scope.
"""

from __future__ import annotations

from frappe.model.document import Document


class ScopeItem(Document):
	pass

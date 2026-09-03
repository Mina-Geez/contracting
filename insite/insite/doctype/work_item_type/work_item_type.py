"""Work Item Type — a kind of work, and the accounts it posts to.

How the work is measured lives on its Measurement Rules, which are their own
records so each can name the fields it reads. The form lists them under
Measurement.
"""

from __future__ import annotations

from frappe.model.document import Document


class WorkItemType(Document):
	pass

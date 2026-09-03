"""Measurement Input — one field a formula reads, and the name it uses for it.

The row stores the fieldname, which is stable, and carries the label only for
display. A formula therefore survives someone renaming a field's label.
The parent Measurement Rule does the validating.
"""

from __future__ import annotations

from frappe.model.document import Document


class MeasurementInput(Document):
	pass

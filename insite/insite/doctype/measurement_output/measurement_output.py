"""Measurement Output — another number the same measurements produce.

A door is billed per leaf, but the workshop also needs the board it consumes,
the edging round it and the ironmongery that goes on it. Those come from the
same measurements, so a rule can write them onto the line beside the billed
quantity. The parent Measurement Rule does the validating.
"""

from __future__ import annotations

from frappe.model.document import Document


class MeasurementOutput(Document):
	pass

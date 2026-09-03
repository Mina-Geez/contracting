"""Measurement Rule — how one item, or group of items, is measured.

Validation lives on the parent Work Item Type, which can check a rule against
its siblings. The controller still has to exist — Frappe imports a module for
every DocType, child tables included.
"""
from __future__ import annotations

from frappe.model.document import Document


class MeasurementRule(Document):
	pass

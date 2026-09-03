"""Role-based price visibility.

v1: a safe, idempotent stub that reads the setting and does nothing when
disabled. The full permlevel-raise implementation is intentionally deferred
(it is not on the delivery-spine critical path) but the hook is wired so the
setting exists and can be turned on later without a schema change.
"""
from __future__ import annotations
import frappe


def apply_from_settings():
    settings = frappe.get_single("Contracting Settings")
    if not settings.enable_price_visibility:
        return
    # Deferred: raise permlevel on selling price/amount fields for the listed roles.
    frappe.logger("insite").info("price visibility enabled; permlevel application deferred to a later phase")

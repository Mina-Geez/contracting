"""Role-based price visibility — NOT ENFORCED YET.

The setting exists so the intent is visible on the roadmap, but the permlevel
work that would actually hide prices is a later phase. Until then the field is
read-only in the UI (see contracting_settings.json) so nobody can switch it on
and believe prices are restricted when they are not.
"""

from __future__ import annotations

import frappe


def apply_from_settings():
	"""No-op placeholder kept so install/migrate wiring stays stable."""
	if frappe.db.get_single_value("Contracting Settings", "enable_price_visibility"):
		frappe.logger("insite").warning(
			"Price visibility is switched on but this release does not enforce it."
		)

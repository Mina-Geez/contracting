"""doc_events handlers for sales/purchase transactions.

Wired in hooks.py as ``before_validate`` on every contracting transaction so the
computed qty is in place BEFORE ERPNext's own ``validate`` recalculates amounts
and taxes. Runs for normally-entered rows and for get_mapped_doc-carried rows
alike (the latter never fire client triggers, which is why this must be server
side).
"""

from __future__ import annotations

import frappe

from contracting.calc import engine


def recalculate(doc, method=None):
	"""before_validate hook: recompute dimension-driven line quantities."""
	# Belt-and-braces: never let a calc error block saving a whole document in a
	# way that is hard to diagnose. Surface config/formula errors to the user
	# (frappe.throw inside the engine), but log unexpected failures.
	try:
		engine.recalculate_document(doc)
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(
			title="Contracting: calc engine error",
			message=frappe.get_traceback(),
		)
		raise

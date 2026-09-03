"""doc_events for sales and purchase transactions.

Two responsibilities, both server-authoritative:

1. `recalculate` — work out measured quantities before ERPNext totals the
   document. Sell-side only: purchases carry the Scope tag for cost
   attribution, but their quantities are what the buyer ordered, not a derived
   measurement.
2. `enforce_project_scope` — keep contracting work traceable. It applies ONLY
   to lines the measurement engine matched, so ordinary sales on the same site
   are unaffected, and it can be switched off in Contracting Settings.

The document lists live in `insite.constants`, which hooks.py reads too, so the
hooks and the handlers can never drift apart.
"""

from __future__ import annotations

import frappe
from frappe import _

from insite.calc import engine
from insite.constants import ENFORCED_DOCTYPES, MEASURED_DOCTYPES


def recalculate(doc, method=None):
	"""before_validate: recompute measured line quantities (drafts only)."""
	if doc.doctype not in MEASURED_DOCTYPES or doc.docstatus != 0:
		return
	try:
		engine.recalculate_document(doc)
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(title="Insite: measurement engine error", message=frappe.get_traceback())
		raise


def enforce_project_scope(doc, method=None):
	"""validate: require a Project, and a Scope that belongs to it.

	A line counts as contracting when the engine matched a rule to it in
	`before_validate` (which stamps `custom_calc_source`). Documents with no
	such lines are left alone.
	"""
	if doc.doctype not in ENFORCED_DOCTYPES:
		return
	if not frappe.db.get_single_value("Contracting Settings", "enforce_project_and_scope"):
		return

	rows = [row for row in (doc.get("items") or []) if row.get("custom_calc_source")]
	if not rows:
		return

	if not doc.get("project"):
		frappe.throw(
			_(
				"Add a Project in the header before you save this {0}. Insite tracks contracting work by project."
			).format(_(doc.doctype)),
			title=_("Project Required"),
		)

	missing = [row for row in rows if not row.get("scope_item")]
	if missing:
		frappe.throw(
			_("Choose a Scope on {0}. Insite tracks contracting work by scope of work.").format(
				_rows_phrase(missing)
			),
			title=_("Scope Required"),
		)

	_check_scopes_belong_to_document(doc, rows)


def _check_scopes_belong_to_document(doc, rows):
	"""A Scope from another project or company would misreport the job."""
	names = {row.scope_item for row in rows if row.get("scope_item")}
	if not names:
		return
	scopes = {
		s.name: s
		for s in frappe.get_all(
			"Scope Item",
			filters={"name": ["in", list(names)]},
			fields=["name", "project", "company", "scope_title"],
		)
	}
	for row in rows:
		scope = scopes.get(row.scope_item)
		if not scope:
			continue
		if scope.project and doc.get("project") and scope.project != doc.project:
			frappe.throw(
				_("Row {0}: the Scope '{1}' belongs to project {2}, but this document is for {3}.").format(
					row.idx, scope.scope_title or scope.name, scope.project, doc.project
				),
				title=_("Scope Belongs to Another Project"),
			)
		if scope.company and doc.get("company") and scope.company != doc.company:
			frappe.throw(
				_("Row {0}: the Scope '{1}' belongs to company {2}, but this document is for {3}.").format(
					row.idx, scope.scope_title or scope.name, scope.company, doc.company
				),
				title=_("Scope Belongs to Another Company"),
			)


def _rows_phrase(rows):
	labels = [f"row {row.idx}" + (f" ({row.item_code})" if row.get("item_code") else "") for row in rows]
	if len(labels) == 1:
		return labels[0]
	return ", ".join(labels[:-1]) + _(" and ") + labels[-1]

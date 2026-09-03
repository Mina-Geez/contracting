"""doc_events for sales and purchase transactions.

Three responsibilities, all server-authoritative:

1. `recalculate` — work out measured quantities before ERPNext totals the
   document. Sell-side only: purchases carry the Scope tag for cost
   attribution, but their quantities are what the buyer ordered, not a derived
   measurement.
2. `enforce_project_scope` — keep contracting work traceable. It applies ONLY
   to lines the measurement engine matched, so ordinary sales on the same site
   are unaffected, and it can be switched off in Insite Settings.
3. `warn_open_rejections` — say so when a Sales Invoice bills a scope that
   still has rejected work on it.

The document lists live in `insite.constants`, which hooks.py reads too, so the
hooks and the handlers can never drift apart.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import escape_html

from insite.calc import engine
from insite.constants import ENFORCED_DOCTYPES, MEASURED_DOCTYPES, REJECTION_OPEN

#: How many rejections to name before the message just says there are more.
REJECTIONS_NAMED = 5


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
	if not frappe.db.get_single_value("Insite Settings", "enforce_project_and_scope"):
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


def warn_open_rejections(doc, method=None):
	"""validate: don't let a Sales Invoice quietly bill work that was rejected.

	A draft is only ever warned about, even when the site is set to refuse:
	someone has to be able to save the invoice they are looking at and sort the
	rejection out afterwards. The refusal lands on submit, which is where the
	money is. A credit note is exempt either way — raising one is how a
	rejection gets closed.

	The rejections are read with `get_all` rather than `get_list` on purpose: a
	sales user who cannot open a Rejection must still be told the work is
	disputed. Only the names and summaries are shown, never anything the reader
	could not already see on the invoice in front of them.
	"""
	if doc.doctype != "Sales Invoice" or doc.get("is_return"):
		return

	scopes = {row.scope_item for row in (doc.get("items") or []) if row.get("scope_item")}
	if not scopes:
		return

	# One query for the document, not one per row.
	rejections = frappe.get_all(
		"Rejection",
		filters={"scope_item": ["in", sorted(scopes)], "status": REJECTION_OPEN},
		fields=["name", "rejection_summary"],
		order_by="reported_on asc",
		limit_page_length=REJECTIONS_NAMED + 1,
	)
	if not rejections:
		return

	message = _build_rejection_message(rejections)
	title = _("Rejected Work on This Scope")
	submitting = doc.docstatus == 1
	if submitting and frappe.db.get_single_value("Insite Settings", "block_invoicing_with_open_rejections"):
		frappe.throw(message, title=title)
	frappe.msgprint(message, title=title, indicator="orange")


def _build_rejection_message(rejections):
	lines = [
		f"<b>{escape_html(r.name)}</b> — {escape_html(r.rejection_summary or '')}"
		for r in rejections[:REJECTIONS_NAMED]
	]
	if len(rejections) > REJECTIONS_NAMED:
		lines.append(_("…and more."))

	opening = _("This invoice covers work with rejections still open:")
	closing = _("Close them, or invoice only the work that was accepted.")
	body = "<br>".join(lines)
	return f"{opening}<br><br>{body}<br><br>{closing}"


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

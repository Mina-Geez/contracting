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
   still has rejected work on it. Rejected work is ERPNext's own Quality
   Inspection; Insite adds a Scope to it and reads it back here.

The document lists live in `insite.constants`, which hooks.py reads too, so the
hooks and the handlers can never drift apart.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import escape_html, flt

from insite.calc import engine
from insite.constants import (
	ENFORCED_DOCTYPES,
	MEASURED_DOCTYPES,
	QI_REJECTED,
	QUALITY_INSPECTION,
)

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

	Rejected work is a submitted Quality Inspection still marked Rejected.
	Insite adds only the Scope to it; ERPNext owns the rest.

	A draft is only ever warned about, even when the site is set to refuse:
	someone has to be able to save the invoice they are looking at and sort the
	inspection out afterwards. The refusal lands on submit, which is where the
	money is. A credit note is exempt either way — raising one is a way of
	settling the argument.

	The inspections are read with `get_all` rather than `get_list` on purpose: a
	sales user who cannot open a Quality Inspection must still be told the work
	is disputed. Only the name and item are shown, neither of which the reader
	could not already see on the invoice in front of them.
	"""
	if doc.doctype != "Sales Invoice" or doc.get("is_return"):
		return

	scopes = {row.scope_item for row in (doc.get("items") or []) if row.get("scope_item")}
	if not scopes:
		return

	# One query for the document, not one per row.
	rejected = frappe.get_all(
		QUALITY_INSPECTION,
		filters={
			"scope_item": ["in", sorted(scopes)],
			"status": QI_REJECTED,
			"docstatus": 1,
		},
		fields=["name", "item_name", "item_code", "custom_rejected_qty"],
		order_by="report_date asc",
		limit_page_length=REJECTIONS_NAMED + 1,
	)
	if not rejected:
		return

	message = _build_rejection_message(rejected)
	title = _("Rejected Work on This Scope")
	submitting = doc.docstatus == 1
	if submitting and frappe.db.get_single_value("Insite Settings", "block_invoicing_with_open_rejections"):
		frappe.throw(message, title=title)
	frappe.msgprint(message, title=title, indicator="orange")


def set_the_plan_from_the_first_commitment(doc, method=None):
	"""on_submit: fill a scope's Planned Amount from the document that set it.

	Nobody knows a scope's value when they create it, and typing a number
	twice is how two numbers come to disagree. The plan is whatever first
	committed the work: a Quotation where one was sent, the Sales Order where
	the customer ordered over the phone.

	Only fills a blank. Once a scope has a planned amount it is the agreed
	baseline, and later documents are variations measured against it — that is
	what Variance to Plan reads. A contractor who re-agrees the contract value
	edits the scope, and Frappe keeps the history.
	"""
	totals = {}
	for row in doc.get("items") or []:
		if row.get("scope_item"):
			totals[row.scope_item] = totals.get(row.scope_item, 0) + flt(row.get("base_amount"))
	if not totals:
		return

	planned = frappe.get_all(
		"Scope Item",
		filters={"name": ["in", sorted(totals)]},
		fields=["name", "planned_amount"],
	)
	for scope in planned:
		if flt(scope.planned_amount):
			continue  # already agreed; later documents are variations against it
		record = frappe.get_doc("Scope Item", scope.name)
		record.planned_amount = totals[scope.name]
		record.save(ignore_permissions=True)
		frappe.msgprint(
			_("{0} is now planned at {1}, from this {2}. Edit the scope to change it.").format(
				record.scope_title or record.name,
				frappe.utils.fmt_money(totals[scope.name], currency=doc.get("currency")),
				_(doc.doctype),
			),
			title=_("Scope Planned"),
			indicator="blue",
			alert=True,
		)


def _build_rejection_message(inspections):
	lines = []
	for inspection in inspections[:REJECTIONS_NAMED]:
		what = inspection.item_name or inspection.item_code or ""
		quantity = flt(inspection.custom_rejected_qty)
		measure = f"{quantity:g} × " if quantity else ""
		lines.append(f"<b>{escape_html(inspection.name)}</b> — {escape_html(measure + what)}")
	if len(inspections) > REJECTIONS_NAMED:
		lines.append(_("…and more."))

	opening = _("This invoice covers work that failed inspection and is still rejected:")
	closing = _("Settle them, or invoice only the work that was accepted.")
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

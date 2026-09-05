"""doc_events for sales and purchase transactions.

Three responsibilities, all server-authoritative:

1. `recalculate` — work out measured quantities before ERPNext totals the
   document. Sell-side only: purchases carry the Scope tag for cost
   attribution, but their quantities are what the buyer ordered, not a derived
   measurement.
2. `enforce_project_scope` — keep contracting work traceable. It applies ONLY
   to lines the measurement engine matched, so ordinary sales on the same site
   are unaffected, and it can be switched off in Insite Settings.
3. `set_the_plan_from_the_first_order` — a scope's planned value is the
   first order on it.
4. `warn_open_rejections` — say so when a Sales Invoice bills a scope that
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
	"""before_validate: recompute measured line quantities (drafts only).

	**A return is never recalculated.** Its quantities are negative — that is
	what makes it a return — and a measurement formula can only produce a
	positive number. The engine used to overwrite the mapped -42 with +42, and
	ERPNext then refused the document outright: "at least one item should be
	entered with negative quantity". No credit note or return of measured work
	could be recorded at all, and the only way through was to clear the
	measurements, which threw away the record of what came back.

	So the measurements ride along as a description of what was returned, and
	the quantity stays what the return says it is.
	"""
	if doc.doctype not in MEASURED_DOCTYPES or doc.docstatus != 0:
		return
	if doc.get("is_return"):
		return
	try:
		engine.recalculate_document(doc)
	except frappe.ValidationError:
		raise
	except Exception:
		frappe.log_error(title="Insite: measurement engine error", message=frappe.get_traceback())
		raise


def drop_the_stamp_when_the_quantity_stops_matching(doc, method=None):
	"""on_update_after_submit: never claim a measurement produced a quantity it did not.

	ERPNext's "Update Items" rewrites `qty` on a submitted order. The engine
	cannot follow it there — recalculating a submitted document would change
	what was approved — so the line kept its old stamp and the Measurement
	Register printed "40 off x H 2 x W 1.5 — Quantity 5", which is a lie about a
	shipment.

	The quantity is left exactly as ERPNext set it. What goes is Insite's claim
	to have worked it out.
	"""
	changed = []
	for row in doc.get("items") or []:
		if not row.get("custom_calc_source"):
			continue
		calculated = flt(row.get("custom_calculated_qty"))
		if not calculated or flt(row.get("qty"), 3) == flt(calculated, 3):
			continue
		for field in ("custom_calculated_qty", "custom_calc_measure", "custom_calc_source"):
			row.db_set(field, None, update_modified=False)
		changed.append(row.idx)

	if changed:
		frappe.msgprint(
			_(
				"The quantity on {0} no longer comes from the measurements, so Insite has stopped claiming it does. The measurements are still recorded."
			).format(_rows_phrase([frappe._dict(idx=idx) for idx in changed])),
			title=_("No Longer Measured"),
			indicator="orange",
		)


def keep_scopes_on_their_own_project(doc, method=None):
	"""validate: a line that names a Scope must name one from this document's project.

	This is a consistency check, not a requirement to carry a scope, so it runs
	on **every** tagged document — the purchase side included — and on every
	line, measured or not.

	Both of those used to be false, and the hole was wide. The old check looked
	only at lines the engine had matched a rule to, so a scope from another job
	sailed through on any ordinary line — prelims, plant hire, labour, freight,
	which every contractor has. Purchase documents were never checked at all, so
	one job's costs could be committed against another's scope. A cost landed on
	a scope whose own project's Measurement Register could not show it, because
	that report filters by the document's project and Contract Progress filters
	by the scope's.
	"""
	rows = [row for row in (doc.get("items") or []) if row.get("scope_item")]
	if rows:
		_check_scopes_belong_to_document(doc, rows)


def enforce_project_scope(doc, method=None):
	"""validate: require a Project, and a Scope, on measured lines.

	A line counts as contracting when the engine matched a rule to it in
	`before_validate` (which stamps `custom_calc_source`). Documents with no
	such lines are left alone — ordinary sales still work.

	Consistency between a scope and its project is checked separately, on every
	line and every document, by `keep_scopes_on_their_own_project`.
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


def forget_the_plan_when_the_order_goes(doc, method=None):
	"""on_cancel: a cancelled order is not a plan.

	The plan only ever fills a blank, and nothing used to react to a
	cancellation — so a scope went on claiming a baseline from a document that
	no longer existed, and Contract Progress read "Variance to Plan -50,000"
	against nothing. Amending then made it worse: the corrected order read as a
	variation against the figure it superseded.

	Cleared only when no submitted order is left on the scope, so cancelling one
	order of several does not throw away a baseline the others still support.
	The amended document sets it again on submit, which is the right answer: an
	amendment is a correction, not a variation.
	"""
	scopes = {row.scope_item for row in (doc.get("items") or []) if row.get("scope_item")}
	for scope in sorted(scopes):
		if _another_order_still_stands(scope, doc.name):
			continue
		if flt(frappe.db.get_value("Scope Item", scope, "planned_amount")):
			frappe.db.set_value("Scope Item", scope, "planned_amount", 0, update_modified=False)


def _another_order_still_stands(scope, except_order):
	"""Is any other submitted Sales Order still carrying this scope?"""
	rows = frappe.get_all(
		"Sales Order Item",
		filters={"scope_item": scope, "docstatus": 1, "parent": ["!=", except_order]},
		pluck="parent",
		limit=1,
	)
	return bool(rows)


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


def set_the_plan_from_the_first_order(doc, method=None):
	"""on_submit: fill a scope's Planned Amount from the first Sales Order on it.

	Nobody knows a scope's value when they create it, and typing a number
	twice is how two numbers come to disagree. The order is the commitment —
	a quotation means nothing until it has been ordered, and plenty of work is
	ordered over the phone with no quotation at all.

	Only fills a blank. Once a scope has a planned amount it is the agreed
	baseline, and later orders are variations measured against it — that is
	what Variance to Plan reads. A contractor who re-agrees the contract value
	edits the scope, and Frappe keeps the history.
	"""
	totals = {}
	for row in doc.get("items") or []:
		if row.get("scope_item"):
			totals[row.scope_item] = totals.get(row.scope_item, 0) + flt(row.get("base_net_amount"))
	if not totals:
		return

	# The totals are base_net_amount, so the plan is in the company's currency
	# and net of any discount — the price the customer actually agreed. Gross
	# recorded a baseline nobody signed, and every Variance to Plan after it was
	# measured against that. An order raised in another currency was also being
	# announced at its company-currency value under the foreign symbol.
	home_currency = frappe.get_cached_value("Company", doc.company, "default_currency")

	# Sorted so two documents touching the same scopes lock them in the same
	# order and cannot deadlock against each other.
	for name in sorted(totals):
		# Locked before it is read. Reading first and writing after is a race:
		# two orders submitted at the same moment both see a blank plan, both
		# write, and the second one wins — leaving the baseline set by the wrong
		# order for the life of the contract, with every Variance to Plan
		# measured against it. The lock is by primary key, so it is one row.
		if flt(frappe.db.get_value("Scope Item", name, "planned_amount", for_update=True)):
			continue  # already agreed; later documents are variations against it

		record = frappe.get_doc("Scope Item", name)
		record.planned_amount = totals[name]
		record.save(ignore_permissions=True)
		frappe.msgprint(
			_("{0} is now planned at {1}, from this order. Edit the scope to change it.").format(
				record.scope_title or record.name,
				frappe.utils.fmt_money(totals[name], currency=home_currency),
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

"""Whitelisted endpoints for the Insite desk UI."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import flt

from insite.calc import engine
from insite.calc.measures import MANUAL, evaluate_formula
from insite.calc.resolve import resolve_rule


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=60, seconds=60)
def preview_formula(formula: str, values: str | dict | None = None):
	"""Work out one quantity from sample numbers.

	Backs the "Try it" button on a Measurement Rule, so a rule can be checked
	before anyone relies on it. Reads nothing and writes nothing.
	"""
	frappe.only_for(["Contracting Manager", "System Manager"])
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	numbers = {str(token): flt(value) for token, value in values.items()}
	try:
		return evaluate_formula(formula, numbers)
	except ValueError as e:
		frappe.throw(str(e), title=_("Formula Problem"))
	except ArithmeticError:
		frappe.throw(
			_("That formula cannot be worked out with these numbers."),
			title=_("Formula Problem"),
		)


@frappe.whitelist(methods=["POST"])
def add_scopes(project: str, titles: str):
	"""Create several Scope Items on a project from a list of titles.

	A job has six or ten scopes and opening a form for each is the dullest part
	of setting Insite up. Titles arrive one per line.

	A title already on the project is skipped rather than duplicated: two scopes
	with the same name would split the same work across two rows of Contract
	Progress and nobody would know which was which. Nothing else is set — the
	planned amount fills itself from the first sales order on each scope.
	"""
	frappe.only_for(["Contracting Manager", "System Manager"])
	if not frappe.has_permission("Scope Item", "create"):
		frappe.throw(_("You are not allowed to create a Scope Item."), frappe.PermissionError)
	project_doc = frappe.get_doc("Project", project)  # also checks read permission

	wanted, seen = [], set()
	for line in (titles or "").splitlines():
		title = line.strip()
		if title and title.casefold() not in seen:
			seen.add(title.casefold())
			wanted.append(title)
	if not wanted:
		frappe.throw(_("Type at least one scope, one per line."), title=_("Nothing to Add"))

	existing = {
		title.casefold()
		for title in frappe.get_all("Scope Item", filters={"project": project}, pluck="scope_title")
	}

	created, already_there = [], []
	for title in wanted:
		if title.casefold() in existing:
			already_there.append(title)
			continue
		scope = frappe.get_doc(
			{
				"doctype": "Scope Item",
				"scope_title": title,
				"project": project_doc.name,
				"status": "Active",
			}
		).insert()
		created.append(scope.name)

	return {"created": created, "already_there": already_there}


@frappe.whitelist()
def line_preview(item_code: str | None = None, values: str | dict | None = None):
	"""What a line needs, and what it comes to.

	The form asks as soon as an item is chosen and again as measurements are
	typed, so a line only shows the boxes it needs and the quantity keeps up
	with what someone is entering. The server decides again when the document
	is saved — this only saves the user from working blind until then.

	Any user who can raise a document may ask. It reveals nothing beyond which
	fields to show and the arithmetic they are already entitled to see.
	"""
	blank = {"inputs": "", "quantity": None, "rule": None}
	if not item_code:
		return blank

	rules = engine.load_rules()
	if not rules:
		return blank

	item = _item_for(item_code)
	if not item:
		return blank

	rule = resolve_rule(item, rules)
	if not rule:
		return {"inputs": engine.NOTHING_MEASURED, "quantity": None, "rule": None}

	answer = {
		"inputs": ",".join(engine.line_fields_used(rule)) or engine.NOTHING_MEASURED,
		"quantity": None,
		"rule": rule["title"],
	}
	if rule["preset"] == MANUAL:
		return answer

	line = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	numbers = engine.read_inputs(frappe._dict(line), rule, _item_values_for(item_code, rule))
	if not [value for value in numbers.values() if value]:
		return answer  # nothing measured yet
	try:
		answer["quantity"] = flt(evaluate_formula(rule["formula"], numbers), 3)
	except (ValueError, ArithmeticError):
		pass  # the rule is being edited, or the numbers do not work yet
	return answer


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def scope_query(doctype, txt, searchfield, start, page_len, filters, reference_doctype=None):
	"""The Scope picker on a document line: ERPNext's own list, narrowed to the project.

	`scope_item` is an Accounting Dimension, so ERPNext puts its own search on
	the field — one that honours Accounting Dimension Filters, skips disabled
	scopes and keeps to the company. Worth keeping.

	What it will not do is narrow by project. It reads `dimension`, `account`
	and `company` out of the filters and ignores every other key, so a `project`
	added to them is silently dropped and the picker offers every scope in the
	company. Someone then chooses a scope from another job and the server
	refuses the document at save, having offered the choice in the first place.

	So: run theirs, then keep the names that are on this project. A project has
	a handful of scopes, which is the smaller set to fetch and compare against.
	"""
	from erpnext.controllers.queries import get_filtered_dimensions

	filters = frappe._dict(filters or {})
	project = filters.pop("project", None)
	rows = get_filtered_dimensions(doctype, txt, searchfield, start, page_len, filters, reference_doctype)
	if not project:
		return rows

	on_project = set(
		frappe.get_all("Scope Item", filters={"project": project}, pluck="name", limit_page_length=0)
	)
	return [row for row in rows if row[0] in on_project]


def _item_for(item_code):
	values = frappe.get_cached_value(
		"Item", item_code, ["item_group", "variant_of", "has_variants"], as_dict=True
	)
	if not values:
		return None
	attributes = {
		row.attribute: row.attribute_value
		for row in frappe.get_all(
			"Item Variant Attribute",
			filters={"parent": item_code},
			fields=["attribute", "attribute_value"],
		)
	}
	return {
		"item_code": item_code,
		"item_group": values.get("item_group"),
		"variant_of": values.get("variant_of"),
		"has_variants": values.get("has_variants"),
		"attributes": attributes,
	}


def _item_values_for(item_code, rule):
	fields = engine.item_fields_used(rule)
	if not fields:
		return {}
	return frappe.get_cached_value("Item", item_code, fields, as_dict=True) or {}

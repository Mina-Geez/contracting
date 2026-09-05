"""Remove the Work Item Type, keeping every rule's name.

It was a name and a switch with no logic behind it — three fields and a `pass`
controller — and it stood between an implementor and their first rule as a
mandatory link. Good UX is turning five steps into two. What it did is already
done elsewhere: a rule has its own title and its own Disabled, and what a rule
covers is said by Applies To.

Titles are preserved rather than rebuilt. `rule_title` is a stored field and it
already reads "Glass · Glazing" on every existing rule, so this leaves it exactly
as the site has it — a name someone has been reading for months should not change
because the model behind it did.

**This runs in `pre_model_sync`, and deletes at the table level on purpose.**
The doctype's Python files are gone by the time a site upgrades, so the moment
anything asks Frappe to load the doctype it dies with "Module import failed for
Work Item Type". `frappe.delete_doc` loads the controller to run `on_trash`, so
it cannot be used to clean up after files that no longer exist — it is the thing
that breaks. Model sync would hit the same wall, which is why this is not a
post-sync patch.

Idempotent: safe to re-run, and a no-op on a site installed after the removal.
"""

import frappe

DOCTYPE = "Work Item Type"
TABLE = "tabWork Item Type"


def execute():
	_keep_the_titles()
	_drop_the_link()
	_drop_the_doctype()


def _keep_the_titles():
	"""Name any rule that somehow has none, before the source of one goes."""
	if not frappe.db.has_column("Measurement Rule", "work_item_type"):
		return

	frappe.db.sql(
		"""update `tabMeasurement Rule`
		   set rule_title = work_item_type
		   where ifnull(rule_title, '') = '' and ifnull(work_item_type, '') != ''"""
	)


def _drop_the_link():
	"""The column goes, and anything that customised it."""
	if frappe.db.has_column("Measurement Rule", "work_item_type"):
		frappe.db.sql_ddl("alter table `tabMeasurement Rule` drop column `work_item_type`")

	frappe.db.delete("Property Setter", {"doc_type": "Measurement Rule", "field_name": "work_item_type"})
	frappe.db.delete("Custom Field", {"dt": "Measurement Rule", "fieldname": "work_item_type"})
	frappe.db.delete("DocField", {"parent": "Measurement Rule", "fieldname": "work_item_type"})


def _drop_the_doctype():
	"""Remove the definition and its table without ever loading the controller."""
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	for doctype, filters in (
		("DocField", {"parent": DOCTYPE}),
		("DocPerm", {"parent": DOCTYPE}),
		("Custom Field", {"dt": DOCTYPE}),
		("Property Setter", {"doc_type": DOCTYPE}),
		("Report", {"ref_doctype": DOCTYPE}),
	):
		frappe.db.delete(doctype, filters)

	frappe.db.delete("DocType", {"name": DOCTYPE})
	frappe.db.sql_ddl(f"drop table if exists `{TABLE}`")
	frappe.clear_cache(doctype=DOCTYPE)

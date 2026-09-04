# Imported under a private name: Frappe turns every public module-level name in
# this file into a hook, and these are configuration, not hooks.
from insite import constants as _c

app_name = "insite"
app_title = "Insite"
app_publisher = "Inspect Solutions"
app_description = "Contracting for ERPNext: measured quantities, scopes and progress."
app_email = "mina@inspect-solutions.com"
app_license = "MIT"

# Insite reads and extends ERPNext's sales and purchase documents, so the site
# must have ERPNext before this app can install.
required_apps = ["frappe", "erpnext"]

# --- Where Insite appears ---------------------------------------------------
add_to_apps_screen = [
	{
		"name": "insite",
		"logo": "/assets/insite/images/logo.svg",
		"title": "Insite",
		"route": "/app/insite",
	}
]

# --- Install / migrate ------------------------------------------------------
after_install = "insite.install.after_install"
after_migrate = "insite.install.after_migrate"

# --- Client scripts ---------------------------------------------------------
doctype_js = {dt: "public/js/insite_transaction.js" for dt in _c.TAGGED_DOCTYPES}
doctype_js["Measurement Rule"] = "public/js/measurement_rule.js"
doctype_js["Work Item Type"] = "public/js/work_item_type.js"
doctype_js["Project"] = "public/js/project.js"

# --- Document events (server-authoritative) ---------------------------------
# Quantities are computed before ERPNext totals the document; the Project and
# Scope check runs afterwards, once the engine has marked the measured rows.
doc_events = {
	dt: {"before_validate": "insite.overrides.transaction.recalculate"} for dt in _c.MEASURED_DOCTYPES
}

for _doctype in _c.ENFORCED_DOCTYPES:
	doc_events.setdefault(_doctype, {})["validate"] = ["insite.overrides.transaction.enforce_project_scope"]

del _doctype

# Billing is where rejected work costs money, so that is where Insite speaks up.
doc_events["Sales Invoice"]["validate"].append("insite.overrides.transaction.warn_open_rejections")

# Rejected work is ERPNext's Quality Inspection. Insite gives it a Scope and
# works out what the refused quantity was worth.
doc_events["Quality Inspection"] = {"validate": ["insite.overrides.quality_inspection.price_the_rejection"]}

fixtures = []

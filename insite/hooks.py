from insite.constants import ENFORCED_DOCTYPES, MEASURED_DOCTYPES, TAGGED_DOCTYPES

app_name = "insite"
app_title = "Insite"
app_publisher = "Inspect Solutions"
app_description = "Contracting for ERPNext: measured quantities, scopes, variations and progress."
app_email = "mina@inspect-solutions.com"
app_license = "MIT"

# Insite reads and extends ERPNext's sales and purchase documents, so the site
# must have ERPNext before this app can install.
required_apps = ["frappe", "erpnext"]

# --- Install / migrate ------------------------------------------------------
after_install = "insite.install.after_install"
after_migrate = "insite.install.after_migrate"

# --- Client scripts ---------------------------------------------------------
doctype_js = {dt: "public/js/insite_transaction.js" for dt in TAGGED_DOCTYPES}
doctype_js["Work Item Type"] = "public/js/work_item_type.js"

# --- Document events (server-authoritative) ---------------------------------
# Quantities are computed before ERPNext totals the document; the Project and
# Scope check runs afterwards, once the engine has marked the measured rows.
doc_events = {dt: {"before_validate": "insite.overrides.transaction.recalculate"}
              for dt in MEASURED_DOCTYPES}

for _doctype in ENFORCED_DOCTYPES:
	doc_events.setdefault(_doctype, {})["validate"] = "insite.overrides.transaction.enforce_project_scope"

del _doctype

fixtures = []

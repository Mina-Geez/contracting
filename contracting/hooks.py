app_name = "contracting"
app_title = "Contracting"
app_publisher = "Inspect Solutions"
app_description = (
	"Generic, UI-configurable contracting vertical for Frappe/ERPNext v16 — "
	"onboard any trade (glass, wood/joinery, aluminium, civil) by configuration, not code."
)
app_email = "mina@inspect-solutions.com"
app_license = "gpl-3.0"

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
# Ensures erpnext (and frappe) are installed when someone installs this app.
required_apps = ["frappe", "erpnext"]

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
add_to_apps_screen = [
	{
		"name": "contracting",
		"logo": "/assets/contracting/images/logo.svg",
		"title": "Contracting",
		"route": "/app/contracting",
	}
]

# ---------------------------------------------------------------------------
# Includes in <head> — bundled JS/CSS (upgrade-safe; replaces DB Client Scripts)
# ---------------------------------------------------------------------------
# Global desk JS (live-UX recompute helpers). Bundles resolve via *.bundle.js.
app_include_js = "contracting.bundle.js"

# Per-doctype client scripts. The same generic transaction script is attached to
# every sales/purchase document that carries dimension-driven line items.
doctype_js = {
	"Quotation": "public/js/contracting_transaction.js",
	"Sales Order": "public/js/contracting_transaction.js",
	"Delivery Note": "public/js/contracting_transaction.js",
	"Sales Invoice": "public/js/contracting_transaction.js",
	"Material Request": "public/js/contracting_transaction.js",
	"Supplier Quotation": "public/js/contracting_transaction.js",
	"Purchase Order": "public/js/contracting_transaction.js",
	"Purchase Receipt": "public/js/contracting_transaction.js",
	"Purchase Invoice": "public/js/contracting_transaction.js",
}

# ---------------------------------------------------------------------------
# Document Events (server-authoritative)
# ---------------------------------------------------------------------------
# The calc engine computes line qty in `before_validate` so that ERPNext's own
# `validate` -> calculate_taxes_and_totals runs AFTER our qty is set. This also
# guarantees correctness for get_mapped_doc-inserted child rows, which never fire
# client-side field triggers.
_CONTRACTING_TXNS = list(doctype_js.keys())

doc_events = {
	dt: {"before_validate": "contracting.overrides.transaction.recalculate"}
	for dt in _CONTRACTING_TXNS
}

# ---------------------------------------------------------------------------
# Install / migrate — idempotent, code-defined setup (no fixtures of standard
# doctypes, no Export-Customizations custom/*.json sync).
# ---------------------------------------------------------------------------
after_install = "contracting.install.after_install"
after_migrate = "contracting.install.after_migrate"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
# Intentionally empty. The Calculation Method registry is seeded idempotently in
# code (install.py). Trade Profiles / Calculation Rules / Contract Clauses are
# site-specific config and are NOT shipped as fixtures (they would drag in
# site-local accounts/warehouses). See DECISIONS.md.
fixtures = []

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
# before_tests = "contracting.tests.utils.before_tests"

app_name = "insite"
app_title = "Insite"
app_publisher = "Inspect Solutions"
app_description = "Configuration-driven contracting vertical for ERPNext"
app_email = "mina@inspect-solutions.com"
app_license = "MIT"

# Extended in later tasks:
after_install = "insite.install.after_install"
after_migrate = "insite.install.after_migrate"

# --- Transaction JS ---------------------------------------------------------
_INSITE_TXNS = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice",
                "Material Request", "Supplier Quotation", "Purchase Order",
                "Purchase Receipt", "Purchase Invoice"]

doctype_js = {dt: "public/js/insite_transaction.js" for dt in _INSITE_TXNS}
doctype_js["Work Item Type"] = "public/js/work_item_type.js"

# --- Document Events (server-authoritative) --------------------------------
doc_events = {dt: {"before_validate": "insite.overrides.transaction.recalculate"} for dt in _INSITE_TXNS}
for _dt in ["Sales Order", "Delivery Note", "Sales Invoice"]:
    doc_events[_dt]["validate"] = "insite.overrides.transaction.enforce_project_scope"

fixtures = []

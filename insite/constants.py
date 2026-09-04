"""Document types Insite attaches to.

Kept free of imports so `hooks.py` can read it without pulling in the engine,
and so the lists exist in exactly one place — hooks, the doc events and the
custom fields all derive from here rather than repeating themselves.
"""

#: Documents whose quantities are derived from measurements.
MEASURED_DOCTYPES = ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice")

#: Buying-side documents. They carry the Scope tag for cost attribution, but
#: their quantities are entered, not measured.
BUYING_DOCTYPES = (
	"Material Request",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
)

#: Everything Insite touches.
TAGGED_DOCTYPES = MEASURED_DOCTYPES + BUYING_DOCTYPES

#: Documents that must carry a Project and a Scope on measured lines. A
#: Quotation stays free — at that stage the job may not exist yet.
ENFORCED_DOCTYPES = ("Sales Order", "Delivery Note", "Sales Invoice")

#: The item child tables that receive the measurement and audit fields.
ITEM_DOCTYPES = tuple(f"{doctype} Item" for doctype in TAGGED_DOCTYPES)

#: Where a Measurement Rule input gets its number. Kept here so the doctype's
#: options and the engine's comparisons cannot drift apart.
INPUT_FROM_LINE = "Line"
INPUT_FROM_ITEM = "Item"
INPUT_CONSTANT = "Constant"
INPUT_SOURCES = (INPUT_FROM_LINE, INPUT_FROM_ITEM, INPUT_CONSTANT)

#: Rejected work is ERPNext's **Quality Inspection**, not a doctype of our own.
#: It already carries the status, who inspected it, who verified it, the
#: remarks and the readings, and both Delivery Note Item and Sales Invoice Item
#: already link to one. Insite only adds what it lacks: a Scope, and how much
#: was rejected.
QUALITY_INSPECTION = "Quality Inspection"

#: The status that means the work is still refused. ERPNext's own options are
#: Accepted / Rejected / Cancelled — compared against, never written by us.
QI_REJECTED = "Rejected"
QI_ACCEPTED = "Accepted"

#: Where an outgoing inspection can hang. Insite reads these to price a
#: rejection from the line it came off.
QI_SELL_SIDE_REFERENCES = ("Delivery Note", "Sales Invoice")

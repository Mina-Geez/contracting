// Insite — transaction lines.
//
// Quantities are worked out on the server when the document is saved, so this
// script deliberately does no arithmetic. It only makes the form react when a
// measurement changes, so the user can see there is something to save.

const INSITE_MEASUREMENT_FIELDS = [
	"custom_base_qty",
	"custom_height",
	"custom_width",
	"custom_length",
	"custom_waste_factor",
];

const INSITE_ITEM_DOCTYPES = [
	"Quotation Item",
	"Sales Order Item",
	"Delivery Note Item",
	"Sales Invoice Item",
	"Material Request Item",
	"Supplier Quotation Item",
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
];

INSITE_ITEM_DOCTYPES.forEach((doctype) => {
	const handlers = {};
	INSITE_MEASUREMENT_FIELDS.forEach((fieldname) => {
		handlers[fieldname] = (frm) => frm.dirty();
	});
	frappe.ui.form.on(doctype, handlers);
});

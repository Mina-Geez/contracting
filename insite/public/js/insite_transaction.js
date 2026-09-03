// Insite — transaction lines.
//
// Quantities are worked out on the server when the document is saved, so this
// script does no arithmetic. It has two small jobs: ask which measurement
// boxes a line actually needs as soon as an item is chosen, so a door does not
// offer a length nobody will fill in, and make the form react when a
// measurement changes so there is something to save.

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

// One answer per item, kept for the life of the page.
const insite_inputs_cache = {};

function insite_apply_inputs(cdt, cdn, item_code) {
	if (!item_code) return;
	const use = (value) => frappe.model.set_value(cdt, cdn, "custom_measurement_inputs", value);
	if (item_code in insite_inputs_cache) {
		use(insite_inputs_cache[item_code]);
		return;
	}
	frappe.call({
		method: "insite.api.inputs_for_item",
		args: { item_code: item_code },
		callback(r) {
			insite_inputs_cache[item_code] = r.message || "";
			use(insite_inputs_cache[item_code]);
		},
	});
}

INSITE_ITEM_DOCTYPES.forEach((doctype) => {
	const handlers = {
		item_code(frm, cdt, cdn) {
			insite_apply_inputs(cdt, cdn, locals[cdt][cdn].item_code);
		},
	};
	INSITE_MEASUREMENT_FIELDS.forEach((fieldname) => {
		handlers[fieldname] = (frm) => frm.dirty();
	});
	frappe.ui.form.on(doctype, handlers);
});

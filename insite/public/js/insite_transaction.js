// Insite — transaction lines.
//
// The server decides the quantity when the document is saved. This script
// keeps the person entering the document from working blind until then: it
// asks which measurement boxes the line needs, shows the quantity as they
// type, offers only the scopes that belong to this project, and carries the
// scope down to the next line.

const INSITE_MEASUREMENT_FIELDS = [
	"custom_base_qty",
	"custom_height",
	"custom_width",
	"custom_length",
	"custom_waste_factor",
];

// Quantities are derived on these. A purchase line carries the Scope for cost,
// but its quantity is what was ordered, so nothing here may touch it.
const INSITE_MEASURED_DOCTYPES = ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"];

const INSITE_BUYING_DOCTYPES = [
	"Material Request",
	"Supplier Quotation",
	"Purchase Order",
	"Purchase Receipt",
	"Purchase Invoice",
];

const INSITE_PARENT_DOCTYPES = INSITE_MEASURED_DOCTYPES.concat(INSITE_BUYING_DOCTYPES);

function insite_refresh_line(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row || !row.item_code) return;

	const values = {};
	INSITE_MEASUREMENT_FIELDS.forEach((fieldname) => {
		values[fieldname] = row[fieldname] || 0;
	});

	frappe.call({
		method: "insite.api.line_preview",
		args: { item_code: row.item_code, values: values },
		callback(r) {
			const answer = r.message;
			if (!answer) return;
			frappe.model.set_value(cdt, cdn, "custom_measurement_inputs", answer.inputs);
			if (answer.quantity !== null && answer.quantity !== undefined) {
				frappe.model.set_value(cdt, cdn, "qty", answer.quantity);
			}
		},
	});
}

INSITE_PARENT_DOCTYPES.forEach((parent) => {
	const child = `${parent} Item`;

	frappe.ui.form.on(parent, {
		onload(frm) {
			// Never offer a scope from another project: the document would be
			// refused on save, and the picker should not have suggested it.
			frm.set_query("scope_item", "items", () => ({
				filters: frm.doc.project ? { project: frm.doc.project } : {},
			}));
		},
	});

	const measured = INSITE_MEASURED_DOCTYPES.includes(parent);

	const handlers = {
		item_code(frm, cdt, cdn) {
			if (measured) insite_refresh_line(frm, cdt, cdn);
		},
		items_add(frm, cdt, cdn) {
			// Most lines on a document belong to the same scope. Carry it down
			// rather than making someone pick it forty times.
			const rows = frm.doc.items || [];
			const previous = rows[rows.length - 2];
			if (previous && previous.scope_item) {
				frappe.model.set_value(cdt, cdn, "scope_item", previous.scope_item);
			}
		},
	};

	if (measured) {
		INSITE_MEASUREMENT_FIELDS.forEach((fieldname) => {
			handlers[fieldname] = (frm, cdt, cdn) => insite_refresh_line(frm, cdt, cdn);
		});
	}

	frappe.ui.form.on(child, handlers);
});

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

// Open a new Rejection for one line of this delivery, already filled in. A
// delivery usually has many lines and only one of them was rejected, so ask
// which — guessing would put the rejection against the wrong scope.
function insite_report_rejection(frm) {
	const rows = (frm.doc.items || []).filter((row) => row.item_code);
	if (!rows.length) return;

	const choices = rows.map((row) => ({
		label: `${row.idx}. ${row.item_name || row.item_code} — ${format_number(row.qty)} ${row.uom || ""}`,
		value: String(row.idx),
	}));

	const dialog = new frappe.ui.Dialog({
		title: __("Report a Rejection"),
		fields: [
			{
				fieldname: "idx",
				label: __("Which line was rejected?"),
				fieldtype: "Select",
				options: choices,
				default: choices[0].value,
				reqd: 1,
			},
			{
				fieldname: "rejected_qty",
				label: __("How much of it?"),
				fieldtype: "Float",
				reqd: 1,
			},
		],
		primary_action_label: __("Continue"),
		primary_action(values) {
			const row = rows.find((r) => String(r.idx) === values.idx);
			dialog.hide();
			frappe.model.with_doctype("Rejection", () => {
				const rejection = frappe.model.get_new_doc("Rejection");
				Object.assign(rejection, {
					project: frm.doc.project,
					company: frm.doc.company,
					scope_item: row.scope_item,
					item_code: row.item_code,
					rejected_qty: values.rejected_qty,
					rate: row.rate,
					delivery_note: frm.doc.name,
				});
				frappe.set_route("Form", "Rejection", rejection.name);
			});
		},
	});
	dialog.show();
}

INSITE_PARENT_DOCTYPES.forEach((parent) => {
	const child = `${parent} Item`;

	const parent_handlers = {
		onload(frm) {
			// Never offer a scope from another project: the document would be
			// refused on save, and the picker should not have suggested it.
			frm.set_query("scope_item", "items", () => ({
				filters: frm.doc.project ? { project: frm.doc.project } : {},
			}));
		},
	};

	// A rejection is always about work that actually went out, so the button
	// belongs on a submitted delivery and nowhere else.
	if (parent === "Delivery Note") {
		parent_handlers.refresh = (frm) => {
			if (frm.doc.docstatus !== 1) return;
			frm.add_custom_button(__("Report a Rejection"), () => insite_report_rejection(frm));
		};
	}

	frappe.ui.form.on(parent, parent_handlers);

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

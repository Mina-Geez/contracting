// Live UX for dimension-driven line quantities.
//
// Client JS is for UX only — the server before_validate hook is authoritative.
// We mirror the server engine here so the grid updates immediately: on change of
// a dimension field we ask the server to resolve the rule + compute qty, then
// write it with frappe.model.set_value (NOT row.qty = x, which would not fire
// calculate_taxes_and_totals).

frappe.provide("contracting");

contracting.CHILD_DOCTYPES = [
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

contracting.TRIGGER_FIELDS = [
	"item_code",
	"custom_height",
	"custom_width",
	"custom_length",
	"custom_base_qty",
	"custom_waste_factor",
];

contracting.recompute_row = function (frm, cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.item_code) return;

	const values = {
		custom_height: row.custom_height,
		custom_width: row.custom_width,
		custom_length: row.custom_length,
		custom_base_qty: row.custom_base_qty,
		custom_waste_factor: row.custom_waste_factor,
		qty: row.qty,
	};

	frappe.call({
		method: "contracting.api.compute_row_qty",
		args: { item_code: row.item_code, values: JSON.stringify(values) },
		callback: function (r) {
			const res = (r && r.message) || {};
			if (res.skip || res.qty === undefined || res.qty === null) return;

			const target = res.target_field || "qty";
			frappe.model.set_value(cdt, cdn, target, res.qty);
			if (target !== "custom_calculated_qty") {
				frappe.model.set_value(cdt, cdn, "custom_calculated_qty", res.qty);
			}
			frappe.model.set_value(cdt, cdn, "custom_calc_method", res.method);
			frappe.model.set_value(cdt, cdn, "custom_calc_rule", res.rule);
		},
	});
};

// Register change handlers on every contracting item child table. Registering
// across all child doctypes from a file loaded per-parent is idempotent.
contracting.CHILD_DOCTYPES.forEach(function (dt) {
	const handlers = {};
	contracting.TRIGGER_FIELDS.forEach(function (field) {
		handlers[field] = function (frm, cdt, cdn) {
			contracting.recompute_row(frm, cdt, cdn);
		};
	});
	frappe.ui.form.on(dt, handlers);
});

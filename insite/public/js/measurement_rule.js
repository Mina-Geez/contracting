// Insite — Measurement Rule.
//
// Two jobs: offer the fields that actually exist on a transaction line, and
// let someone try a rule with sample numbers before a real document relies on
// it. The arithmetic is done on the server by the same code that runs on a
// live document, so what you see here is what you get.

frappe.ui.form.on("Measurement Rule", {
	onload(frm) {
		insite_load_fields(frm);
	},

	refresh(frm) {
		insite_load_fields(frm);
		if (!frm.is_new()) {
			frm.add_custom_button(__("Try it"), () => insite_try_dialog(frm));
		}
	},

	preset(frm) {
		if (!frm.doc.preset || frm.doc.preset === "Custom") return;
		if (frm.doc.preset === "Manual") {
			frm.clear_table("inputs");
			frm.set_value("formula", "");
			frm.refresh_field("inputs");
			return;
		}
		frappe.call({
			method: "insite.insite.doctype.measurement_rule.measurement_rule.get_preset",
			args: { name: frm.doc.preset },
			callback(r) {
				if (!r.message) return;
				frm.clear_table("inputs");
				(r.message.inputs || []).forEach((row) => {
					const child = frm.add_child("inputs");
					child.field_name = row.field_name;
					child.field_label = row.field_label;
					child.token = row.token;
				});
				frm.refresh_field("inputs");
				frm.set_value("formula", r.message.formula || "");
			},
		});
	},
});

frappe.ui.form.on("Measurement Input", {
	field_name(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const match = (frm.__insite_fields || []).find((f) => f.value === row.field_name);
		if (!match) return;
		frappe.model.set_value(cdt, cdn, "field_label", match.label);
		if (!row.token) {
			frappe.model.set_value(cdt, cdn, "token", insite_suggest_token(match.label));
		}
	},
});

// Ask the server which number fields the line actually has, and offer those.
function insite_load_fields(frm) {
	if (frm.__insite_fields) {
		insite_apply_field_options(frm);
		return;
	}
	frappe.call({
		method: "insite.insite.doctype.measurement_rule.measurement_rule.get_measurable_fields",
		callback(r) {
			frm.__insite_fields = r.message || [];
			insite_apply_field_options(frm);
		},
	});
}

function insite_apply_field_options(frm) {
	const grid = frm.fields_dict.inputs && frm.fields_dict.inputs.grid;
	if (!grid) return;
	const df = grid.get_docfield("field_name");
	if (df) df.get_data = () => frm.__insite_fields || [];
}

function insite_suggest_token(label) {
	const token = (label || "")
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "_")
		.replace(/^_+|_+$/g, "");
	return !token || /^[0-9]/.test(token) ? `f_${token}` : token;
}

function insite_try_dialog(frm) {
	const inputs = (frm.doc.inputs || []).filter((row) => row.token);
	if (!frm.doc.formula || !inputs.length) {
		frappe.msgprint(__("Add the inputs and a formula first."));
		return;
	}
	const dialog = new frappe.ui.Dialog({
		title: __("Try this rule"),
		fields: inputs.map((row) => ({
			fieldname: row.token,
			label: `${row.field_label || row.field_name} (${row.token})`,
			fieldtype: "Float",
		})),
		primary_action_label: __("Work it out"),
		primary_action(values) {
			frappe.call({
				method: "insite.api.preview_formula",
				args: { formula: frm.doc.formula, values: values },
				callback(r) {
					frappe.msgprint({
						title: __("Quantity"),
						message: __("This rule gives a quantity of {0}.", [format_number(r.message)]),
						indicator: "blue",
					});
				},
			});
		},
	});
	dialog.show();
}

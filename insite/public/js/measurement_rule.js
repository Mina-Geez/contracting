// Insite — Measurement Rule.
//
// Three jobs: fill in the starting point so a new rule opens ready to save,
// offer only the fields that actually exist for each input's source, and let
// someone try the rule with sample numbers. The arithmetic is done on the
// server by the same code that runs on a live document, so what you see here
// is what you get.

frappe.ui.form.on("Measurement Rule", {
	onload(frm) {
		insite_load_fields(frm);
		// A new rule opens with a starting point already chosen. Fill it in, or
		// keeping the sensible default would save to "add at least one input".
		if (frm.is_new() && frm.doc.preset && !(frm.doc.inputs || []).length) {
			insite_apply_preset(frm);
		}
	},

	refresh(frm) {
		insite_load_fields(frm);
		// Available before saving too: trying a rule is how you find out
		// whether it is worth saving.
		frm.add_custom_button(__("Try it"), () => insite_try_dialog(frm));
	},

	preset(frm) {
		insite_apply_preset(frm);
	},
});

frappe.ui.form.on("Measurement Output", {
	field_name(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const known = (frm.__insite_fields || {}).Line || [];
		const match = known.find((f) => f.value === row.field_name);
		if (match) frappe.model.set_value(cdt, cdn, "field_label", match.label);
	},
});

frappe.ui.form.on("Measurement Input", {
	source(frm, cdt, cdn) {
		// The field list differs per source, so start the row over.
		frappe.model.set_value(cdt, cdn, "field_name", null);
		frappe.model.set_value(cdt, cdn, "field_label", null);
	},

	field_name(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const source = row.source || "Line";
		const known = (frm.__insite_fields || {})[source] || [];
		const match = known.find((f) => f.value === row.field_name);
		if (!match) return;
		frappe.model.set_value(cdt, cdn, "field_label", match.label);
		if (!row.token) {
			frappe.model.set_value(cdt, cdn, "token", insite_suggest_token(match.label));
		}
	},
});

function insite_apply_preset(frm) {
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
				child.source = "Line";
				child.field_name = row.field_name;
				child.field_label = row.field_label;
				child.token = row.token;
			});
			frm.refresh_field("inputs");
			frm.set_value("formula", r.message.formula || "");
		},
	});
}

// Ask the server which number fields exist, for each place a rule can read from.
function insite_load_fields(frm) {
	if (frm.__insite_fields) {
		insite_apply_field_options(frm);
		return;
	}
	frm.__insite_fields = {};
	["Line", "Item"].forEach((source) => {
		frappe.call({
			method: "insite.insite.doctype.measurement_rule.measurement_rule.get_measurable_fields",
			args: { source: source },
			callback(r) {
				frm.__insite_fields[source] = r.message || [];
				insite_apply_field_options(frm);
			},
		});
	});
}

function insite_apply_field_options(frm) {
	const inputs = frm.fields_dict.inputs && frm.fields_dict.inputs.grid;
	if (inputs) {
		const df = inputs.get_docfield("field_name");
		if (df) {
			df.get_data = (txt, row) => {
				const source = (row && row.source) || "Line";
				return (frm.__insite_fields || {})[source] || [];
			};
		}
	}

	// An output is always written onto the line.
	const outputs = frm.fields_dict.outputs && frm.fields_dict.outputs.grid;
	if (outputs) {
		const df = outputs.get_docfield("field_name");
		if (df) df.get_data = () => (frm.__insite_fields || {}).Line || [];
	}
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

	// Only ask for what a person would actually measure. Item numbers and
	// constants are filled in for them, so the dialog stays short.
	const asked = inputs.filter((row) => (row.source || "Line") === "Line");
	const given = {};
	inputs.forEach((row) => {
		if ((row.source || "Line") === "Constant") given[row.token] = row.constant_value || 0;
	});

	const dialog = new frappe.ui.Dialog({
		title: __("Try this rule"),
		fields: asked.map((row) => ({
			fieldname: row.token,
			label: `${row.field_label || row.field_name} (${row.token})`,
			fieldtype: "Float",
		})),
		primary_action_label: __("Work it out"),
		primary_action(values) {
			const numbers = Object.assign({}, given, values);
			inputs.forEach((row) => {
				if (numbers[row.token] === undefined) numbers[row.token] = 1;
			});
			frappe.call({
				method: "insite.api.preview_formula",
				args: { formula: frm.doc.formula, values: numbers },
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

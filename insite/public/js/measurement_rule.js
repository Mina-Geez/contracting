// Insite — Measurement Rule.
//
// Four jobs: fill in the starting point so a new rule opens ready to save,
// offer only the fields that actually exist for each input's source, let
// someone add a field that does not exist yet without leaving the rule, and let
// them try the rule with sample numbers. The arithmetic is done on the server
// by the same code that runs on a live document, so what you see here is what
// you get.

// Picked from the field list to make a new field instead of choosing one. Not a
// fieldname anything could collide with.
const INSITE_ADD_FIELD = "__insite_add_field";

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

	formula(frm) {
		insite_show_summary(frm);
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
	inputs_remove(frm) {
		insite_show_summary(frm);
	},

	token(frm) {
		insite_show_summary(frm);
	},

	source(frm, cdt, cdn) {
		// The field list differs per source, so start the row over.
		frappe.model.set_value(cdt, cdn, "field_name", null);
		frappe.model.set_value(cdt, cdn, "field_label", null);
	},

	field_name(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const source = row.source || "Line";

		if (row.field_name === INSITE_ADD_FIELD) {
			// Not a choice — a request to make one. Put the cell back and ask.
			frappe.model.set_value(cdt, cdn, "field_name", null);
			insite_add_field_dialog(frm, cdt, cdn, source);
			return;
		}

		const known = (frm.__insite_fields || {})[source] || [];
		const match = known.find((f) => f.value === row.field_name);
		if (!match) return;
		frappe.model.set_value(cdt, cdn, "field_label", match.label);
		if (!row.token) {
			frappe.model.set_value(cdt, cdn, "token", insite_suggest_token(match.label));
		}
		insite_show_summary(frm);
	},
});

// Say the formula in the words on the form, so nobody has to read code.
function insite_show_summary(frm) {
	let text = frm.doc.formula || "";
	const rows = (frm.doc.inputs || []).slice();
	// Longest names first, so "count" inside "panel_count" is not replaced.
	rows.sort((a, b) => (b.token || "").length - (a.token || "").length);
	rows.forEach((row) => {
		if (!row.token) return;
		const label =
			row.source === "Constant"
				? String(row.constant_value || "")
				: row.field_label || row.token;
		text = text.replace(new RegExp(`\\b${row.token}\\b`, "g"), label);
	});
	frm.set_value("measurement_summary", text.replace(/\*/g, "×").trim());
}

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
			insite_show_summary(frm);
		},
	});
}

// The number a rule needs does not always exist yet, and making one used to
// mean leaving the rule half-written, opening Measurement Field, coming back and
// finding your place. The field list offers to make it here instead. Where it
// belongs is not asked: the row already says whether the number is measured on
// the line or held on the Item, and asking twice is how the two disagree.
function insite_add_field_dialog(frm, cdt, cdn, source) {
	const on_the_item = source === "Item";
	const dialog = new frappe.ui.Dialog({
		title: __("Add a new field"),
		fields: [
			{
				fieldname: "field_label",
				label: __("Label"),
				fieldtype: "Data",
				reqd: 1,
				description: on_the_item
					? __("Added to the Item, for a number that is true of the material.")
					: __("Added to every transaction line, for a number measured on site."),
			},
			{ fieldname: "help_text", label: __("Help Text"), fieldtype: "Small Text" },
		],
		primary_action_label: __("Add it"),
		primary_action(values) {
			dialog.hide();
			frappe.db
				.insert({
					doctype: "Measurement Field",
					field_label: values.field_label,
					applies_to: on_the_item ? "Item" : "Transaction line",
					help_text: values.help_text,
				})
				.then((doc) => {
					// Setting the fieldname runs the handler above, which fills
					// in the label and suggests the name for the formula.
					insite_load_fields(frm, source, () => {
						frappe.model.set_value(cdt, cdn, "field_name", doc.field_name);
					});
					frappe.show_alert({
						message: __("{0} is now on every document that needs it.", [doc.field_label]),
						indicator: "green",
					});
				});
		},
	});
	dialog.show();
}

// Ask the server which number fields exist, for each place a rule can read from.
// Pass a source to re-ask for just that one, after adding a field to it.
function insite_load_fields(frm, only, done) {
	if (frm.__insite_fields && !only) {
		insite_apply_field_options(frm);
		return;
	}
	frm.__insite_fields = frm.__insite_fields || {};
	(only ? [only] : ["Line", "Item"]).forEach((source) => {
		frappe.call({
			method: "insite.insite.doctype.measurement_rule.measurement_rule.get_measurable_fields",
			args: { source: source },
			callback(r) {
				frm.__insite_fields[source] = r.message || [];
				insite_apply_field_options(frm);
				if (done) done();
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
				const fields = (frm.__insite_fields || {})[source] || [];
				return fields.concat([
					{
						value: INSITE_ADD_FIELD,
						label: __("Add a new field…"),
						description: __("For a number Insite does not ship"),
					},
				]);
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

	// Constants are filled in from the rule. Everything else is asked for,
	// including Item numbers: there is no item here to read them from, and
	// quietly assuming 1 would give an answer that means nothing.
	const asked = inputs.filter((row) => (row.source || "Line") !== "Constant");
	const given = {};
	inputs.forEach((row) => {
		if ((row.source || "Line") === "Constant") given[row.token] = row.constant_value || 0;
	});

	const dialog = new frappe.ui.Dialog({
		title: __("Try this rule"),
		fields: asked.map((row) => ({
			fieldname: row.token,
			label:
				(row.source === "Item" ? `${row.field_label || row.field_name} — on the Item` : row.field_label || row.field_name) +
				` (${row.token})`,
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

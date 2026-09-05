// Insite — how is this measured?
//
// The rules are their own records, targeted the way ERPNext targets a Pricing
// Rule. That is the right shape: a rule is reusable, it carries a priority, and
// it can cover an item group, a brand, a template or one item. What it costs is
// that standing on an Item Group there was nothing at all to say how the things
// in it are measured, so the honest answer to "where do I set this?" was
// "somewhere else, and you have to know it exists".
//
// So the answer lives here too. Not the setting — the answer, and a way to
// reach the record that holds it.

["Item", "Item Group"].forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (frm.is_new()) return;
			insite_show_how_it_is_measured(frm, doctype);
		},
	});
});

function insite_show_how_it_is_measured(frm, doctype) {
	frappe.call({
		method: "insite.api.measured_by",
		args: { doctype: doctype, name: frm.doc.name },
		callback(r) {
			// Cleared first: refresh runs again after every save, and a headline
			// is added rather than replaced, so without this they stack up.
			frm.dashboard.clear_headline();
			const answer = r.message;

			if (!answer) {
				insite_offer_a_rule(frm, doctype);
				return;
			}

			const link = `<a href="/desk/measurement-rule/${encodeURIComponent(answer.rule)}">${frappe.utils.escape_html(answer.title)}</a>`;
			const how = answer.summary ? ` — ${frappe.utils.escape_html(answer.summary)}` : "";
			const message = answer.inherited_from
				? __("Measured by {0}{1}, set on {2}.", [link, how, frappe.utils.escape_html(answer.inherited_from)])
				: __("Measured by {0}{1}.", [link, how]);

			frm.dashboard.set_headline(message, "blue");
			insite_add_button(frm, __("Measurement Rule"), () =>
				frappe.set_route("Form", "Measurement Rule", answer.rule)
			);
		},
	});
}

function insite_offer_a_rule(frm, doctype) {
	frm.dashboard.set_headline(
		__("Nothing measures this yet, so quantities are typed by hand."),
		"orange"
	);
	insite_add_button(frm, __("Measure This"), () => {
		// Open a rule already pointed at what you were looking at.
		const values =
			doctype === "Item Group"
				? { apply_on: "Item Group", item_group: frm.doc.name }
				: { apply_on: "Item Code", item_code: frm.doc.name };
		frappe.new_doc("Measurement Rule", values);
	});
}

function insite_add_button(frm, label, action) {
	// Frappe keeps adding the same button on every refresh otherwise.
	if (frm.custom_buttons[label]) return;
	frm.add_custom_button(label, action, __("Insite"));
}

// Insite — Project.
//
// The Project and the Scope Item are the two things Insite reports against, so
// a project should lead to its scopes rather than making someone start from
// the Scope Item list and pick the project back.

frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Scope Items"), () => {
			frappe.set_route("List", "Scope Item", { project: frm.doc.name });
		}, __("Insite"));

		frm.add_custom_button(__("Add Scopes"), () => insite_add_scopes(frm), __("Insite"));

		frm.add_custom_button(__("Contract Progress"), () => {
			frappe.set_route("query-report", "Contract Progress", { project: frm.doc.name });
		}, __("Insite"));
	},
});

// A job has six or ten scopes, and opening a form for each one is the dullest
// part of setting Insite up. Type the list instead; the planned amounts fill
// themselves from the first order on each.
function insite_add_scopes(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Add Scopes to {0}", [frm.doc.project_name || frm.doc.name]),
		fields: [
			{
				fieldname: "titles",
				label: __("One scope per line"),
				fieldtype: "Small Text",
				reqd: 1,
				description: __(
					"For example: Curtain wall glazing, ACP cladding, Handrails — each on its own line. " +
						"Leave the planned amounts alone; the first sales order on each scope sets them."
				),
			},
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			dialog.get_primary_btn().prop("disabled", true);
			frappe.call({
				method: "insite.api.add_scopes",
				args: { project: frm.doc.name, titles: values.titles },
				freeze: true,
				freeze_message: __("Creating the scopes…"),
				callback(r) {
					dialog.hide();
					const made = (r.message && r.message.created) || [];
					const skipped = (r.message && r.message.already_there) || [];
					const show_them = () =>
						frappe.set_route("List", "Scope Item", { project: frm.doc.name });

					if (!skipped.length) {
						frappe.show_alert(
							{ message: __("{0} scopes added.", [made.length]), indicator: "green" },
							5
						);
						show_them();
						return;
					}

					// Something was left alone, and routing straight to the list
					// buries the only notice that it was.
					frappe.msgprint({
						title: __("Already There"),
						indicator: "orange",
						message: __(
							"{0} added. These were already on the project, so they were left alone: {1}",
							[made.length, skipped.join(", ")]
						),
						primary_action: {
							label: __("Show the scopes"),
							action() {
								frappe.hide_msgprint();
								show_them();
							},
						},
					});
				},
				error() {
					dialog.get_primary_btn().prop("disabled", false);
				},
			});
		},
	});
	dialog.show();
}

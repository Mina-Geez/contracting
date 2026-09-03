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

		frm.add_custom_button(__("New Scope Item"), () => {
			frappe.new_doc("Scope Item", { project: frm.doc.name });
		}, __("Insite"));

		frm.add_custom_button(__("Contract Progress"), () => {
			frappe.set_route("query-report", "Contract Progress", { project: frm.doc.name });
		}, __("Insite"));
	},
});

// Insite — collecting a payment for one job.
//
// "Get Outstanding Invoices" opens a Filters dialog, and ERPNext builds the
// dimension half of that dialog from `frm.dimension_filters`. Every accounting
// dimension is already in there, so the Scope filter exists and works with
// nothing added — Insite registers the Scope as a dimension, and the server
// side of the search reads any active one.
//
// Project is the exception, and ERPNext says so in its own comment on this
// form: "project excluded in setup_dimension_filters". So the dialog never
// offered it. Adding it to the list is all the client needs; the server half is
// in insite/overrides/payment_entry.py, because ERPNext's search ignores a
// project the same way it ignored everything else we have handed it.

frappe.ui.form.on("Payment Entry", {
	onload: insite_offer_a_project_filter,
	refresh: insite_offer_a_project_filter,
});

function insite_offer_a_project_filter(frm) {
	// ERPNext fills this in `setup_dimension_filters`, which runs on refresh.
	// If it has not run yet there is nothing to append to, and the next refresh
	// will come back here.
	if (!Array.isArray(frm.dimension_filters)) return;
	if (frm.dimension_filters.some((d) => d.fieldname === "project")) return;

	frm.dimension_filters.push({
		fieldname: "project",
		label: __("Project"),
		document_type: "Project",
	});
}

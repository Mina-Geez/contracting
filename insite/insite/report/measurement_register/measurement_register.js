// Insite — Measurement Register.

frappe.query_reports["Measurement Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
		{
			fieldname: "scope_item",
			label: __("Scope"),
			fieldtype: "Link",
			options: "Scope Item",
			get_query() {
				const project = frappe.query_report.get_filter_value("project");
				return { filters: project ? { project: project } : {} };
			},
		},
		{
			fieldname: "document_type",
			label: __("Document Type"),
			fieldtype: "Select",
			options: ["", "Sales Order", "Delivery Note", "Sales Invoice"].join("\n"),
		},
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
	],
};

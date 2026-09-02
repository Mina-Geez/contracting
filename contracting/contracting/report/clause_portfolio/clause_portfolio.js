// Filters for the Clause Portfolio script report.
frappe.query_reports["Clause Portfolio"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "status",
			label: __("Clause Status"),
			fieldtype: "Select",
			options: ["", "Draft", "Active", "On Hold", "Completed", "Cancelled"].join("\n"),
		},
	],
};

// Insite — Scope Profitability.

frappe.query_reports["Scope Profitability"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
			get_query() {
				const customer = frappe.query_report.get_filter_value("customer");
				return { filters: customer ? { customer: customer } : {} };
			},
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nDraft\nActive\nOn Hold\nCompleted\nCancelled",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		// A scope that is going to lose money should not need reading twice.
		if (["margin", "margin_pct"].includes(column.fieldname) && data && data.margin < 0) {
			return `<span style="color: var(--red-500)">${formatted}</span>`;
		}
		return formatted;
	},
};

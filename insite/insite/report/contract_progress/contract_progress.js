// Insite — Contract Progress.

frappe.query_reports["Contract Progress"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			// Opened without this it showed every company's scopes at once,
			// unlike its two sibling reports. Default to the user's company.
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
		// The totals line: label the first column and bold the rest.
		if (data && data.is_total) {
			if (column.fieldname === "scope") return `<b>${__("Total")}</b>`;
			return `<b>${default_formatter(value, row, column, data)}</b>`;
		}
		// Show the scope by its title, not its code (SC-2026-…), while keeping
		// the cell a link to the scope. Three reviewers read the code and could
		// not tell one scope from another.
		if (column.fieldname === "scope" && data && data.scope_title) {
			return `<a href="/app/scope-item/${encodeURIComponent(value)}">${frappe.utils.escape_html(
				data.scope_title
			)}</a>`;
		}
		return default_formatter(value, row, column, data);
	},
};

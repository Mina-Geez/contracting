frappe.query_reports["Contract Progress"] = {
  filters: [
    {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company"},
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
    {fieldname: "status", label: __("Status"), fieldtype: "Select",
     options: "\nDraft\nActive\nOn Hold\nCompleted\nCancelled"},
  ],
};

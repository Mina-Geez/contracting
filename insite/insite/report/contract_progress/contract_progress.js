frappe.query_reports["Contract Progress"] = {
  filters: [
    {fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company"},
    {fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project"},
    {fieldname: "status", label: __("Status"), fieldtype: "Select",
     options: "\nDraft\nActive\nOn Hold\nCompleted\nCancelled"},
  ],
};

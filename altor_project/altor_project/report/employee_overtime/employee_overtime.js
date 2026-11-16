// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.query_reports["Employee Overtime"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
        { fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.month_end(), reqd: 1 },
        { fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
        { fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
        { fieldname: "worker_type", label: __("Worker Type"), fieldtype: "Select", options: ["", "Own Staff", "Outsourced"].join("\n") },
        { fieldname: "supplier", label: __("Manpower Supplier"), fieldtype: "Link", options: "Supplier" },
        { fieldname: "group_by", label: __("Group By"), fieldtype: "Select", options: ["Employee", "Employee and Project"].join("\n"), default: "Employee" },
    ],
};

// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.query_reports["Project Budget Variance"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
        { fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
        { fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
        {
            fieldname: "budget_status", label: __("Status"), fieldtype: "Select",
            options: ["", "Within Budget", "Warning", "Exceeded"].join("\n")
        },
        { fieldname: "recalculate", label: __("Recalculate Figures Now"), fieldtype: "Check" }
    ],

    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (!data) return value;
        if (column.fieldname === "budget_status") {
            const color = { "Within Budget": "green", "Warning": "orange", "Exceeded": "red" }[data.budget_status];
            if (color) value = `<span class="indicator-pill ${color}">${value}</span>`;
        }
        if (["variance", "utilization_percentage"].includes(column.fieldname)) {
            if (data.budget_status === "Exceeded") value = `<span style="color:var(--red-600);font-weight:600">${value}</span>`;
            else if (data.budget_status === "Warning") value = `<span style="color:var(--orange-600);font-weight:600">${value}</span>`;
        }
        return value;
    }
};

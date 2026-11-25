// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.query_reports["Project Asset Stock"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
        { fieldname: "item_code", label: __("Item"), fieldtype: "Link", options: "Item", get_query: () => ({ filters: { custom_is_project_asset: 1 } }) },
        { fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
        { fieldname: "only_available", label: __("Only Available"), fieldtype: "Check", default: 0 },
    ],
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "available" && data && flt(data.available) <= 0) value = `<span class="text-danger">${value}</span>`;
        return value;
    },
};

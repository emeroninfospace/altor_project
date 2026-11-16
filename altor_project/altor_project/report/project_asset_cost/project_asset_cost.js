// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.query_reports["Project Asset Cost"] = {
    filters: [
        { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
        { fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1 },
        { fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
        { fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
        { fieldname: "cost_center", label: __("Division"), fieldtype: "Link", options: "Cost Center" },
        { fieldname: "project_asset", label: __("Project Asset"), fieldtype: "Link", options: "Project Asset" },
        { fieldname: "item_group", label: __("Item Group"), fieldtype: "Link", options: "Item Group" },
    ],
    onload(report) {
        // Month end: move the depreciation of linked ERPNext Assets used on projects to the projects (Journal Entry)
        report.page.add_inner_button(__("Post Depreciation to Projects"), () => {
            const months = [];
            for (let i = 1; i <= 12; i++) {
                months.push(frappe.datetime.add_months(frappe.datetime.month_start(), -i).slice(0, 7));
            }
            frappe.prompt(
                [
                    { fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", reqd: 1,
                      default: report.get_filter_value("company") || frappe.defaults.get_user_default("Company") },
                    { fieldname: "period", label: __("Month"), fieldtype: "Select", options: months.join("\n"), default: months[0], reqd: 1 },
                ],
                (v) => {
                    frappe.call({
                        method: "altor_project.asset_accounting.post_depreciation_allocation",
                        args: v,
                        freeze: true,
                    }).then((r) => {
                        const out = r.message || {};
                        if (out.journal_entry) {
                            frappe.msgprint(__("{0} Journal Entry {1}", [
                                out.existing ? __("Already posted:") : __("Posted:"),
                                `<a href="/app/journal-entry/${out.journal_entry}">${out.journal_entry}</a>`,
                            ]));
                        } else {
                            frappe.msgprint(out.message || __("Nothing to post."));
                        }
                    });
                },
                __("Post Depreciation to Projects"),
                __("Post")
            );
        });
    },
};

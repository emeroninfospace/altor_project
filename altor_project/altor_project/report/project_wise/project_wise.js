// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.query_reports["Project Wise"] = {
    tree: true,
    name_field: "name",
    parent_field: "parent",
    initial_depth: 0,
    filters: [
        {
            fieldname: "project",
            label: __("Project"),
            fieldtype: "Link",
            options: "Project",
            on_change: () => frappe.query_report.refresh()
        },
        {
            fieldname: "task",
            label: __("Task"),
            fieldtype: "Link",
            options: "Task",
            get_query: function () {
                const project = frappe.query_report.get_filter_value("project");
                return {
                    filters: {
                        project: project || undefined
                    }
                };
            }
        },
        {
            fieldname: "start_date",
            label: __("Start Date"),
            fieldtype: "Date",
            on_change: () => frappe.query_report.refresh()
        },
        {
            fieldname: "end_date",
            label: __("End Date"),
            fieldtype: "Date",
            on_change: () => frappe.query_report.refresh()
        }
    ],

    formatter: function (value, row, column, data, default_formatter) {
			value = default_formatter(value, row, column, data);
			if (!data) return value;

			if (data.indent === 0 && column.fieldname === "project_task") {
				value = `<b>${value}</b>`;
			}

			if (column.fieldname === "assigned_to" && data.assigned_to_ids) {
				const users = data.assigned_to_ids.split(",");
				const names = data.assigned_to.split(",");

				value = users.map((u, i) =>
					`<a href="/app/user/${u.trim()}" target="_blank">${names[i].trim()}</a>`
				).join(", ");
			}

			if (column.fieldname === "priority") {
				if (data.priority === "High") {
					value = `<span style="color:#dc2626;font-weight:600">High</span>`;
				} else if (data.priority === "Medium") {
					value = `<span style="color:#f59e0b;font-weight:600">Medium</span>`;
				} else if (data.priority === "Low") {
					value = `<span style="color:#16a34a;font-weight:600">Low</span>`;
				}
				  else if (data.priority === "Urgent") {
					value = `<span style="color:#b91c1c;font-weight:600">Urgent</span>`;
				}
			}
			return value;
		}
};

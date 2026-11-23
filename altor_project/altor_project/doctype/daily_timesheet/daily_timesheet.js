// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

// Daily Timesheet: one date, many employees; on submit each employee gets a standard Timesheet.
const DEFAULT_HOURS = 8;

frappe.ui.form.on("Daily Timesheet", {
	setup(frm) {
		frm.set_query("project", () => ({ filters: { status: "Open", company: frm.doc.company } }));
		frm.set_query("project", "time_logs", () => ({ filters: { status: "Open", company: frm.doc.company } }));
		frm.set_query("employee", "time_logs", () => ({ filters: { status: "Active", company: frm.doc.company } }));
		frm.set_query("task", "time_logs", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return { filters: row.project ? { project: row.project } : {} };
		});
		frm.set_query("cost_center", () => ({ filters: { is_group: 0, company: frm.doc.company } }));
	},

	refresh(frm) {
		const grid = frm.fields_dict.time_logs.grid;
		grid.update_docfield_property("ot1_hours", "read_only", frm.doc.auto_overtime ? 1 : 0);
		grid.update_docfield_property("ot2_hours", "read_only", frm.doc.auto_overtime ? 1 : 0);

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Add Employees"), () => add_employees(frm));
			if (!frm.doc.time_logs || !frm.doc.time_logs.length) {
				frm.set_intro(__("Pick the date and project, then Add Employees: one row per employee. Submitting makes each employee's Timesheet."), "blue");
			}
		}
		if (frm.doc.docstatus === 1) {
			const sheets = [...new Set((frm.doc.time_logs || []).map((r) => r.timesheet).filter(Boolean))];
			if (sheets.length) {
				frm.add_custom_button(__("Timesheets"), () => {
					frappe.route_options = { name: ["in", sheets] };
					frappe.set_route("List", "Timesheet");
				}, __("View"));
			}
		}
	},

	project(frm) {
		(frm.doc.time_logs || []).forEach((r) => { if (!r.project) frappe.model.set_value(r.doctype, r.name, "project", frm.doc.project); });
	},

	activity_type(frm) {
		(frm.doc.time_logs || []).forEach((r) => { if (!r.activity_type) frappe.model.set_value(r.doctype, r.name, "activity_type", frm.doc.activity_type); });
	},

	auto_overtime(frm) { frm.trigger("refresh"); },
});

frappe.ui.form.on("Daily Timesheet Detail", {
	time_logs_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (frm.doc.project && !row.project) frappe.model.set_value(cdt, cdn, "project", frm.doc.project);
		if (frm.doc.activity_type && !row.activity_type) frappe.model.set_value(cdt, cdn, "activity_type", frm.doc.activity_type);
		if (!row.hours) frappe.model.set_value(cdt, cdn, "hours", DEFAULT_HOURS);
	},
	hours: update_totals,
	employee: update_totals,
	time_logs_remove: update_totals,
});

function update_totals(frm) {
	const rows = frm.doc.time_logs || [];
	frm.set_value("total_employees", new Set(rows.map((r) => r.employee).filter(Boolean)).size);
	frm.set_value("total_hours", rows.reduce((s, r) => s + flt(r.hours), 0));
}

function add_employees(frm) {
	if (!frm.doc.company) {
		frappe.msgprint(__("Select the company first."));
		return;
	}
	const already = new Set((frm.doc.time_logs || []).map((r) => r.employee));
	new frappe.ui.form.MultiSelectDialog({
		doctype: "Employee",
		target: frm,
		setters: { department: null, designation: null },
		get_query: () => ({ filters: { status: "Active", company: frm.doc.company } }),
		add_filters_group: 1,
		primary_action_label: __("Add"),
		action(selections) {
			const picked = (selections || []).filter((e) => !already.has(e));
			if (!picked.length) { this.dialog.hide(); return; }
			frappe.db.get_list("Employee", { filters: { name: ["in", picked] }, fields: ["name", "employee_name"], limit: picked.length })
				.then((list) => {
					const names = Object.fromEntries(list.map((e) => [e.name, e.employee_name]));
					picked.forEach((emp) => {
						const row = frm.add_child("time_logs", {
							employee: emp,
							employee_name: names[emp] || "",
							project: frm.doc.project,
							activity_type: frm.doc.activity_type,
							hours: DEFAULT_HOURS,
						});
						already.add(emp);
						return row;
					});
					frm.refresh_field("time_logs");
					update_totals(frm);
					this.dialog.hide();
				});
		},
	});
}

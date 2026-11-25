// Altor: labour cost on Timesheets (normal / OT 1 / OT 2 hours). The cost is calculated on save
// (altor_project.labour.calculate_timesheet); this keeps Normal Hrs current while typing.

frappe.ui.form.on("Timesheet", {
    // one employee (Employee at the top) or a crew: top empty, an Employee on each row
    employee(frm) {
        (frm.doc.time_logs || []).forEach((r) => frappe.model.set_value(r.doctype, r.name, "custom_employee", frm.doc.employee || r.custom_employee));
    },
    refresh(frm) {
        if (frm.doc.docstatus === 0 && !frm.doc.employee && frm.fields_dict.time_logs.grid.get_docfield("custom_employee")) {
            frm.add_custom_button(__("Add Employees"), () => add_crew(frm));
            if (!(frm.doc.time_logs || []).some((r) => r.custom_employee)) {
                frm.set_intro(__("One employee: choose the Employee at the top. Several employees or projects: leave it empty and use Add Employees (an Employee on each row)."), "blue");
            }
        }
        if (frm.doc.docstatus === 0 && frm.doc.employee && frm.fields_dict.custom_total_labour_cost) {
            frm.set_intro(frm.doc.custom_auto_overtime
                ? __("Overtime is split automatically on save: hours above the normal hours per day (Altor Settings) are OT 1, hours on holidays / weekly off are OT 2.")
                : __("Enter OT 1 and OT 2 hours on each row; the rest of the hours are normal hours."), "blue");
        }
    },
    custom_auto_overtime(frm) {
        frm.refresh_field("time_logs");
        frm.trigger("refresh");
    },
});

frappe.ui.form.on("Timesheet Detail", {
    time_logs_add(frm, cdt, cdn) {
        if (frm.doc.employee) frappe.model.set_value(cdt, cdn, "custom_employee", frm.doc.employee);
    },
    hours: set_normal_hours,
    custom_ot1_hours: set_normal_hours,
    custom_ot2_hours: set_normal_hours,
});

function set_normal_hours(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (frm.doc.custom_auto_overtime || !frm.fields_dict.custom_total_labour_cost) return;
    const ot = flt(row.custom_ot1_hours) + flt(row.custom_ot2_hours);
    if (ot > flt(row.hours)) {
        frappe.show_alert({ message: __("OT hours are more than the hours worked"), indicator: "orange" });
    }
    frappe.model.set_value(cdt, cdn, "custom_normal_hours", Math.max(flt(row.hours) - ot, 0));
}

// crew Timesheet: one row per picked employee, with the last row's project, activity, start and hours
function add_crew(frm) {
    const rows = frm.doc.time_logs || [];
    const last = rows.length ? rows[rows.length - 1] : {};
    const start = last.from_time || `${frappe.datetime.get_today()} 08:00:00`;
    new frappe.ui.form.MultiSelectDialog({
        doctype: "Employee",
        target: frm,
        setters: { department: null, designation: null },
        get_query: () => ({ filters: { status: "Active", company: frm.doc.company } }),
        add_filters_group: 1,
        primary_action_label: __("Add"),
        action(selections) {
            const picked = selections || [];
            if (!picked.length) { this.dialog.hide(); return; }
            frappe.db.get_list("Employee", { filters: { name: ["in", picked] }, fields: ["name", "employee_name"], limit: picked.length })
                .then((list) => {
                    const names = Object.fromEntries(list.map((e) => [e.name, e.employee_name]));
                    // an empty first row (new Timesheet) is used for the first employee
                    const blank = rows.length === 1 && !rows[0].custom_employee && !rows[0].hours ? rows[0] : null;
                    picked.forEach((emp, i) => {
                        const values = {
                            custom_employee: emp, custom_employee_name: names[emp] || "",
                            activity_type: last.activity_type, project: last.project, task: last.task,
                            from_time: start, hours: flt(last.hours) || 8,
                        };
                        if (i === 0 && blank) Object.assign(blank, values);
                        else frm.add_child("time_logs", values);
                    });
                    frm.refresh_field("time_logs");
                    frm.dirty();
                    this.dialog.hide();
                });
        },
    });
}

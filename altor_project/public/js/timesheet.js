// Altor: labour cost on Timesheets (normal / OT 1 / OT 2 hours). The cost is calculated on save
// (altor_project.labour.calculate_timesheet); this keeps Normal Hrs current while typing.

frappe.ui.form.on("Timesheet", {
    refresh(frm) {
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

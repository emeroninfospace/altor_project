// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Manpower Entry", {
    setup(frm) {
        frm.set_query("task", () => ({ filters: { project: frm.doc.project } }));
        frm.set_query("project", () => ({ filters: { status: "Open" } }));
        frm.set_query("employee", "details", (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            const filters = { status: "Active" };
            if (doc.company) filters.company = doc.company;
            if (row.worker_type === "Outsourced") filters.custom_is_outsourced = 1;
            if (row.worker_type === "Own Staff") filters.custom_is_outsourced = 0;
            if (row.worker_type === "Outsourced" && row.supplier) filters.custom_manpower_supplier = row.supplier;
            return { filters };
        });
    },

    onload(frm) {
        if (frm.is_new() && !frm.doc.item_group) {
            frappe.call("altor_project.manpower.get_default_item_group").then((r) => {
                if (r.message && !frm.doc.item_group) frm.set_value("item_group", r.message);
            });
        }
    },

    refresh(frm) {
        if (frm.doc.docstatus === 0 && frm.doc.project) {
            frm.add_custom_button(__("Copy Previous Crew"), () => copy_previous(frm));
        }
        if (frm.doc.project) {
            frm.add_custom_button(__("Manpower Cost Summary"), () => {
                frappe.set_route("query-report", "Manpower Cost Summary", { project: frm.doc.project });
            }, __("View"));
        }
    }
});

frappe.ui.form.on("Manpower Entry Detail", {
    employee(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.employee) return;
        fetch_rates(frm, row, { employee: row.employee });
    },
    worker_type(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.worker_type === "Own Staff") frappe.model.set_value(cdt, cdn, "supplier", "");
        refetch(frm, row);
    },
    supplier(frm, cdt, cdn) { refetch(frm, locals[cdt][cdn]); },
    designation(frm, cdt, cdn) { refetch(frm, locals[cdt][cdn]); },
    no_of_workers: calculate_row,
    working_hours: calculate_row,
    ot_hours: calculate_row,
    hourly_rate: calculate_row,
    ot_hourly_rate: calculate_row,
    details_remove(frm) { calculate_totals(frm); }
});

function refetch(frm, row) {
    if (row.employee) return;
    if (row.worker_type === "Outsourced" && row.supplier) {
        fetch_rates(frm, row, { worker_type: row.worker_type, supplier: row.supplier, designation: row.designation });
    }
}

function fetch_rates(frm, row, args) {
    frappe.call({
        method: "altor_project.manpower.get_worker_details",
        args,
        callback(r) {
            const d = r.message || {};
            const values = { worker_type: d.worker_type, hourly_rate: d.hourly_rate, ot_hourly_rate: d.ot_hourly_rate };
            if (args.employee) {
                values.supplier = d.supplier || "";
                values.designation = d.designation || row.designation;
                values.no_of_workers = 1;
            }
            frappe.model.set_value(row.doctype, row.name, values).then(() => {
                if (!d.hourly_rate) {
                    frappe.show_alert({ message: __("No hourly rate found for row #{0}. Enter it manually.", [row.idx]), indicator: "orange" });
                }
                if (d.employee_status && d.employee_status !== "Active") {
                    frappe.show_alert({ message: __("Employee is {0}", [d.employee_status]), indicator: "orange" });
                }
            });
        }
    });
}

function calculate_row(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const workers = row.no_of_workers == null ? 1 : cint(row.no_of_workers);
    row.amount = flt(workers * (flt(row.working_hours) * flt(row.hourly_rate) + flt(row.ot_hours) * flt(row.ot_hourly_rate)), 2);
    frm.refresh_field("details");
    calculate_totals(frm);
}

function calculate_totals(frm) {
    let workers = 0, hours = 0, ot = 0, own = 0, outsourced = 0;
    (frm.doc.details || []).forEach((d) => {
        const n = cint(d.no_of_workers);
        workers += n;
        hours += flt(d.working_hours) * n;
        ot += flt(d.ot_hours) * n;
        if (d.worker_type === "Outsourced") outsourced += flt(d.amount); else own += flt(d.amount);
    });
    frm.set_value({
        total_workers: workers, total_hours: hours, total_ot_hours: ot,
        own_staff_cost: own, outsourced_cost: outsourced, total_cost: own + outsourced
    });
}

function copy_previous(frm) {
    frappe.call({
        method: "altor_project.altor_project.doctype.manpower_entry.manpower_entry.copy_from_previous",
        args: { project: frm.doc.project, posting_date: frm.doc.posting_date, exclude: frm.is_new() ? null : frm.doc.name },
        callback(r) {
            const rows = r.message || [];
            if (!rows.length) {
                frappe.msgprint(__("No earlier Manpower Entry found for this project."));
                return;
            }
            frm.clear_table("details");
            rows.forEach((d) => frm.add_child("details", d));
            frm.refresh_field("details");
            calculate_totals(frm);
            frappe.show_alert({ message: __("{0} rows copied", [rows.length]), indicator: "green" });
        }
    });
}

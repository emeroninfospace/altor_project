// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

// Same lines and formulas as payment_certificate.py
const PC_LINES = [
    ["A", "Works Executed"],
    ["B", "Variations"],
    ["C", "Material on Site"],
    ["D", "Dayworks"],
    ["F", "Advance Payment"],
    ["G", "Recovery of Advance"],
    ["I", "Retention on Works"],
    ["J", "Retention in Lieu of Performance Bond"],
    ["K", "Release of Retention"],
    ["L", "Financial Assistance / On Account"],
];
const PC_RATE_LINES = ["G", "I", "J"];
const PC_STEPS = ["Draft", "Initiated", "Reviewed", "Checked", "Authorized", "Approved"];
const PC_STATUS_COLOURS = {
    Draft: "gray", Initiated: "blue", Reviewed: "blue", Checked: "purple",
    Authorized: "orange", Approved: "green", Rejected: "red",
};

frappe.ui.form.on("Payment Certificate", {
    setup(frm) {
        frm.set_query("subcontract_work_order", () => ({
            filters: Object.assign(
                { docstatus: ["<", 2] },
                frm.doc.supplier ? { supplier: frm.doc.supplier } : {},
                frm.doc.project ? { project: frm.doc.project } : {}
            ),
        }));
        frm.set_query("project_budget", () => ({
            filters: Object.assign({ docstatus: ["<", 2] }, frm.doc.project ? { project: frm.doc.project } : {}),
        }));
        frm.set_query("cost_center", () => ({
            filters: Object.assign({ is_group: 0 }, frm.doc.company ? { company: frm.doc.company } : {}),
        }));
    },

    onload(frm) {
        if (frm.is_new()) {
            ensure_lines(frm);
            if (!frm.doc.currency && frm.doc.company) set_company_currency(frm);
            if (!(frm.doc.lines || []).some((r) => flt(r.previous))) load_previous(frm);
        }
    },

    refresh(frm) {
        ensure_lines(frm);
        add_approval_buttons(frm);
        if (frm.doc.subcontract_work_order) {
            frm.add_custom_button(__("Subcontract Work Order"), () => {
                frappe.set_route("Form", "Subcontract Work Order", frm.doc.subcontract_work_order);
            }, __("View"));
        }
        if (frm.doc.supplier && frm.doc.project) {
            frm.add_custom_button(__("All Certificates"), () => {
                frappe.set_route("List", "Payment Certificate", {
                    supplier: frm.doc.supplier, project: frm.doc.project,
                });
            }, __("View"));
        }
        if (frm.doc.approval_status && frm.doc.docstatus === 0) {
            frm.page.set_indicator(__(frm.doc.approval_status), PC_STATUS_COLOURS[frm.doc.approval_status] || "gray");
        }
    },

    supplier: load_previous,
    project: load_previous,
    subcontract_work_order: load_previous,
    certificate_date: load_previous,

    company(frm) {
        set_company_currency(frm);
    },
    vat_rate: calculate,
    subcontract_amount: calculate,
    approved_variations: calculate,
    other_adjustments: calculate,
});

frappe.ui.form.on("Payment Certificate Line", {
    cumulative: calculate,
    rate: calculate,
});

frappe.ui.form.on("Payment Certificate Back Charge", {
    amount: calculate_back_charges,
    vat: calculate_back_charges,
    back_charges_remove: calculate_back_charges,
});

function ensure_lines(frm) {
    if (frm.doc.docstatus !== 0) return;
    const refs = (frm.doc.lines || []).map((r) => r.ref).join();
    if (refs === PC_LINES.map((l) => l[0]).join()) return;
    const old = {};
    (frm.doc.lines || []).forEach((r) => (old[r.ref] = r));
    frm.clear_table("lines");
    PC_LINES.forEach(([ref, label]) => {
        const prev = old[ref] || {};
        frm.add_child("lines", {
            ref: ref,
            description: label,
            rate: prev.rate || 0,
            cumulative: prev.cumulative || 0,
            previous: prev.previous || 0,
            notes: prev.notes,
        });
    });
    frm.refresh_field("lines");
}

function set_company_currency(frm) {
    if (!frm.doc.company) return;
    frappe.db.get_value("Company", frm.doc.company, "default_currency").then((r) => {
        if (r.message && r.message.default_currency && !frm.doc.currency) {
            frm.set_value("currency", r.message.default_currency);
        }
    });
}

function load_previous(frm) {
    if (frm.doc.docstatus !== 0) return;
    if (!frm.doc.subcontract_work_order && !(frm.doc.supplier && frm.doc.project)) return;
    frappe.call({
        method: "altor_project.altor_project.doctype.payment_certificate.payment_certificate.get_previous",
        args: {
            supplier: frm.doc.supplier,
            project: frm.doc.project,
            subcontract_work_order: frm.doc.subcontract_work_order,
            certificate_date: frm.doc.certificate_date,
            name: frm.is_new() ? null : frm.doc.name,
        },
    }).then((r) => {
        const data = r.message || {};
        const values = data.values || {};
        ensure_lines(frm);
        (frm.doc.lines || []).forEach((row) => {
            row.previous = flt(values[row.ref]);
            // a new certificate starts from the previous cumulative figures
            if (frm.is_new() && !flt(row.cumulative)) row.cumulative = row.previous;
        });
        frm.doc.previous_certificate = data.certificate || null;
        frm.refresh_field("previous_certificate");
        calculate(frm);
    });
}

function summary(values, vat_rate) {
    const v = {};
    PC_LINES.forEach(([ref]) => (v[ref] = flt(values[ref])));
    const gross = v.A + v.B + v.C + v.D;
    const deductions = v.G + v.I + v.J - v.K - v.L;
    const net = gross + v.F - deductions;
    const vat = flt((net * flt(vat_rate)) / 100, 2);
    return {
        gross: flt(gross, 2),
        remaining_advance: flt(v.F - v.G, 2),
        total_deductions: flt(deductions, 2),
        net_excl_vat: flt(net, 2),
        vat_amount: vat,
        net_incl_vat: flt(net + vat, 2),
    };
}

function calculate(frm) {
    const lines = {};
    (frm.doc.lines || []).forEach((r) => (lines[r.ref] = r));
    if (lines.A && lines.B) {
        const base = flt(lines.A.cumulative) + flt(lines.B.cumulative);
        PC_RATE_LINES.forEach((ref) => {
            const row = lines[ref];
            if (row && flt(row.rate)) row.cumulative = flt((base * flt(row.rate)) / 100, 2);
        });
        if (lines.G && lines.F && flt(lines.G.rate) && flt(lines.G.cumulative) > flt(lines.F.cumulative)) {
            lines.G.cumulative = flt(lines.F.cumulative);
        }
    }
    (frm.doc.lines || []).forEach((r) => {
        r.this_period = flt(flt(r.cumulative) - flt(r.previous), 2);
    });
    frm.refresh_field("lines");

    frm.set_value(
        "revised_contract_amount",
        flt(frm.doc.subcontract_amount) + flt(frm.doc.approved_variations) + flt(frm.doc.other_adjustments)
    );
    ["cumulative", "previous", "this_period"].forEach((column) => {
        const values = {};
        (frm.doc.lines || []).forEach((r) => (values[r.ref] = r[column]));
        const s = summary(values, frm.doc.vat_rate);
        Object.keys(s).forEach((key) => frm.set_value(`${key}_${column}`, s[key]));
    });
}

function calculate_back_charges(frm) {
    let total = 0;
    (frm.doc.back_charges || []).forEach((row) => {
        row.total = flt(flt(row.amount) + flt(row.vat), 2);
        total += row.total;
    });
    frm.refresh_field("back_charges");
    frm.set_value("total_back_charges", flt(total, 2));
}

function add_approval_buttons(frm) {
    if (frm.is_new() || frm.doc.docstatus !== 0) return;
    const status = frm.doc.approval_status || "Draft";
    const i = PC_STEPS.indexOf(status);
    const next = i >= 0 && i < PC_STEPS.length - 1 ? PC_STEPS[i + 1] : status === "Rejected" ? "Initiated" : null;
    if (next) {
        frm.add_custom_button(__("Mark as {0}", [__(next)]), () => set_status(frm, next), __("Approval"));
    }
    if (status !== "Rejected" && status !== "Draft") {
        frm.add_custom_button(__("Reject"), () => {
            frappe.prompt(
                { fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
                (v) => {
                    const remarks = (frm.doc.remarks ? frm.doc.remarks + "\n" : "") + __("Rejected: {0}", [v.reason]);
                    frm.set_value("remarks", remarks);
                    set_status(frm, "Rejected");
                },
                __("Reject Certificate")
            );
        }, __("Approval"));
    }
}

function set_status(frm, status) {
    frm.set_value("approval_status", status);
    frm.save().then(() => {
        if (status === "Approved" && frappe.model.can_submit("Payment Certificate")) {
            frappe.show_alert({ message: __("Approved. You can now submit the certificate."), indicator: "green" });
        }
    });
}

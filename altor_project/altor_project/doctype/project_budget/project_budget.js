// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project Budget Item", {
    budgeted_amount(frm, cdt, cdn) {
        calculate_variance(frm, cdt, cdn);
        calculate_totals(frm);
    },
    actual_amount(frm, cdt, cdn) {
        calculate_variance(frm, cdt, cdn);
        calculate_totals(frm);
    }
});

function calculate_variance(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    let budget = flt(row.budgeted_amount);
    let actual = flt(row.actual_amount);

    row.variance = budget - actual;

    if (budget > 0) {
        row.variance_percentage = ((budget - actual) / budget) * 100;
    } else {
        row.variance_percentage = 0;
    }

    frm.refresh_field("budget_items");
}

function calculate_totals(frm) {
    let total_budget = 0;
    let total_actual = 0;
    let total_variance = 0;

    (frm.doc.budget_items || []).forEach(row => {
        total_budget += flt(row.budgeted_amount);
        total_actual += flt(row.actual_amount);
        total_variance += flt(row.variance);
    });

    frm.set_value('total_estimated_cost', total_budget);
    frm.set_value('total_actual_cost', total_actual);
    frm.set_value('variance', total_variance);

    if (total_budget > 0) {
        frm.set_value(
            'variance_percentage',
            ((total_budget - total_actual) / total_budget) * 100
        );
    } else {
        frm.set_value('variance_percentage', 0);
    }
}

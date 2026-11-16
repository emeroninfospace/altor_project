// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Asset Return", {
    setup(frm) {
        frm.set_query("asset_allocation", () => ({ filters: { docstatus: 1, status: ["!=", "Returned"] } }));
    },

    asset_allocation(frm) {
        if (!frm.doc.asset_allocation || frm.doc.docstatus !== 0) return;
        frappe.call({
            method: "altor_project.altor_project.doctype.asset_allocation.asset_allocation.make_asset_return",
            args: { source_name: frm.doc.asset_allocation },
        }).then((r) => {
            const doc = r.message || {};
            frm.clear_table("items");
            (doc.items || []).forEach((row) => {
                delete row.name;
                frm.add_child("items", row);
            });
            frm.refresh_field("items");
            calculate(frm);
        });
    },

    refresh(frm) {
        if (frm.doc.asset_allocation) {
            frm.add_custom_button(__("Asset Allocation"), () => {
                frappe.set_route("Form", "Asset Allocation", frm.doc.asset_allocation);
            }, __("View"));
        }
    },
});

frappe.ui.form.on("Asset Return Item", {
    returned_qty: check_row,
    damaged_qty: check_row,
    damage_rate: calculate,
    items_remove: calculate,
});

function check_row(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    if (flt(row.returned_qty) + flt(row.damaged_qty) > flt(row.on_site_qty)) {
        frappe.show_alert({ message: __("Only {0} on site", [flt(row.on_site_qty)]), indicator: "orange" });
    }
    calculate(frm);
}

function calculate(frm) {
    let returned = 0, damaged = 0, damage = 0;
    (frm.doc.items || []).forEach((row) => {
        row.damage_cost = flt(flt(row.damaged_qty) * flt(row.damage_rate || row.book_value), 2);
        returned += flt(row.returned_qty);
        damaged += flt(row.damaged_qty);
        damage += row.damage_cost;
    });
    frm.refresh_field("items");
    frm.set_value("total_returned_qty", returned);
    frm.set_value("total_damaged_qty", damaged);
    frm.set_value("total_damage_cost", flt(damage, 2));
}

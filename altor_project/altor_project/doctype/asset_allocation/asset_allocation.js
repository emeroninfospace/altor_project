// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Asset Allocation", {
    setup(frm) {
        frm.set_query("project", () => ({ filters: { status: ["not in", ["Completed", "Cancelled"]] } }));
        frm.set_query("project_asset", "items", () => ({
            filters: Object.assign(
                { disabled: 0, available_qty: [">", 0] },
                frm.doc.company ? { company: frm.doc.company } : {}
            ),
        }));
        frm.set_query("item_code", "items", () => ({ filters: { custom_is_project_asset: 1, disabled: 0 } }));
        frm.set_query("cost_center", () => ({
            filters: Object.assign({ is_group: 0 }, frm.doc.company ? { company: frm.doc.company } : {}),
        }));
    },

    refresh(frm) {
        if (frm.doc.docstatus === 1 && frm.doc.status !== "Returned") {
            frm.add_custom_button(__("Asset Return"), () => {
                frappe.model.open_mapped_doc({
                    method: "altor_project.altor_project.doctype.asset_allocation.asset_allocation.make_asset_return",
                    frm: frm,
                });
            }, __("Create"));
            frm.add_custom_button(__("Refresh Cost to Date"), () => {
                frappe.call({
                    method: "altor_project.altor_project.doctype.asset_allocation.asset_allocation.refresh_figures",
                    args: { name: frm.doc.name },
                }).then(() => frm.reload_doc());
            });
        }
        if (frm.doc.project) {
            frm.add_custom_button(__("Project Asset Cost"), () => {
                frappe.set_route("query-report", "Project Asset Cost", { project: frm.doc.project });
            }, __("View"));
            frm.add_custom_button(__("Project Budget"), () => {
                frappe.set_route("List", "Project Budget", { project: frm.doc.project });
            }, __("View"));
        }
        const colours = { Draft: "gray", Allocated: "blue", "Partly Returned": "orange", Returned: "green", Cancelled: "red" };
        if (frm.doc.docstatus === 1) frm.page.set_indicator(__(frm.doc.status), colours[frm.doc.status] || "gray");
    },
});

frappe.ui.form.on("Asset Allocation Item", {
    item_code(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item_code || row.project_asset) return;
        show_item_stock(frm, cdt, cdn, row.item_code);
    },
    project_asset(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.project_asset) return;
        frappe.db.get_value("Project Asset", row.project_asset,
            ["depreciation_end_date", "item_code", "item_group", "asset_name", "uom"]).then((r) => {
            const v = r.message || {};
            frappe.model.set_value(cdt, cdn, {
                charge_until: v.depreciation_end_date, item_code: v.item_code, item_group: v.item_group,
                asset_name: v.asset_name, uom: v.uom,
            });
            show_item_stock(frm, cdt, cdn, v.item_code);
        });
    },
    qty(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.available_qty != null && flt(row.qty) > flt(row.available_qty)) {
            frappe.show_alert({ message: __("Only {0} available", [flt(row.available_qty)]), indicator: "orange" });
        }
        calculate(frm);
    },
    items_remove: calculate,
});

// available quantity and average rate of the item over all its purchases
function show_item_stock(frm, cdt, cdn, item_code) {
    if (!item_code) return;
    frappe.call({
        method: "altor_project.altor_project.doctype.asset_allocation.asset_allocation.get_item_stock",
        args: { item_code: item_code, company: frm.doc.company },
    }).then((r) => {
        const s = r.message || {};
        frappe.model.set_value(cdt, cdn, {
            available_qty: s.available, daily_rate: s.avg_daily_rate, uom: s.uom, item_group: s.item_group,
            asset_name: s.asset_name,
        });
        calculate(frm);
        frappe.show_alert({
            message: __("{0}: {1} available from {2} purchase(s), average unit cost {3}", [
                s.asset_name || item_code, flt(s.available), s.purchases,
                format_currency(s.avg_unit_cost, frappe.defaults.get_default("currency")),
            ]),
            indicator: flt(s.available) > 0 ? "blue" : "orange",
        }, 7);
    });
}

function calculate(frm) {
    let qty = 0, daily = 0;
    (frm.doc.items || []).forEach((row) => {
        row.daily_amount = flt(flt(row.qty) * flt(row.daily_rate), 2);
        qty += flt(row.qty);
        daily += row.daily_amount;
    });
    frm.refresh_field("items");
    frm.set_value("total_qty", qty);
    frm.set_value("daily_charge", flt(daily, 2));
}

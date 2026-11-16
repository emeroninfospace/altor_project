// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project Asset", {
    setup(frm) {
        frm.set_query("cost_center", () => ({
            filters: Object.assign({ is_group: 0 }, frm.doc.company ? { company: frm.doc.company } : {}),
        }));
    },

    onload(frm) {
        if (frm.is_new() && !frm.doc.company) {
            frm.set_value("company", frappe.defaults.get_user_default("Company"));
        }
    },

    refresh(frm) {
        render_on_projects(frm);
        if (frm.doc.asset) {
            frm.add_custom_button(__("Fixed Asset"), () => frappe.set_route("Form", "Asset", frm.doc.asset), __("View"));
        } else if (!frm.is_new()) {
            frm.dashboard.set_headline_alert(
                __("Not linked to a Fixed Asset, so it is not in the accounts. Link the Asset (created from the GRN) to book its value and depreciation."),
                "orange"
            );
        }
        if (!frm.is_new() && !frm.doc.disabled && flt(frm.doc.available_qty) > 0) {
            frm.add_custom_button(__("Issue to Project"), () => {
                const doc = frappe.model.get_new_doc("Asset Allocation");
                doc.company = frm.doc.company;
                const row = frappe.model.add_child(doc, "items");
                Object.assign(row, {
                    project_asset: frm.doc.name, asset_name: frm.doc.asset_name, uom: frm.doc.uom,
                    item_code: frm.doc.item_code, item_group: frm.doc.item_group,
                    daily_rate: frm.doc.daily_rate, charge_until: frm.doc.depreciation_end_date,
                    available_qty: frm.doc.available_qty,
                });
                frappe.set_route("Form", "Asset Allocation", doc.name);
            }, __("Create"));
        }
        if (!frm.is_new()) {
            frm.add_custom_button(__("Project Asset Cost"), () => {
                frappe.set_route("query-report", "Project Asset Cost", { project_asset: frm.doc.name });
            }, __("View"));
        }
    },

    item_code(frm) {
        if (!frm.doc.item_code || frm.doc.asset_name) return;
        frappe.db.get_value("Item", frm.doc.item_code, "item_name").then((r) => {
            if (r.message) frm.set_value("asset_name", r.message.item_name);
        });
    },
    asset(frm) {
        if (frm.doc.asset) {
            frappe.show_alert({ message: __("Quantity, cost and depreciation are taken from the Asset when you save."), indicator: "blue" });
        }
    },
    qty: calculate,
    unit_cost: calculate,
    salvage_value: calculate,
    depreciation_months: calculate,
    purchase_date: calculate,
});

function calculate(frm) {
    const months = cint(frm.doc.depreciation_months);
    const rate = months > 0 ? Math.max(flt(frm.doc.unit_cost) - flt(frm.doc.salvage_value), 0) / (months * 30) : 0;
    frm.set_value("total_cost", flt(frm.doc.qty) * flt(frm.doc.unit_cost));
    frm.set_value("daily_rate", flt(rate, 4));
    frm.set_value("monthly_rate", flt(rate * 30, 2));
    if (frm.doc.purchase_date && months > 0) {
        frm.set_value("depreciation_end_date", frappe.datetime.add_days(frm.doc.purchase_date, months * 30 - 1));
    }
}

function render_on_projects(frm) {
    const wrapper = frm.get_field("allocations_html").$wrapper;
    const data = frm.doc.__onload || {};
    const rows = data.on_projects || [];
    const money = (v) => format_currency(v, frappe.defaults.get_default("currency"));
    let html = "";
    if (!frm.is_new()) {
        html += `<div class="text-muted small" style="margin-bottom:6px">${__("Book value per unit today")}: <b>${money(data.book_value || 0)}</b></div>`;
    }
    if (rows.length) {
        html += `<table class="table table-bordered table-condensed small"><thead><tr>
            <th>${__("Project")}</th><th>${__("Allocation")}</th><th>${__("Since")}</th>
            <th class="text-right">${__("On Site")}</th><th class="text-right">${__("Depreciation to Date")}</th></tr></thead><tbody>`;
        rows.forEach((r) => {
            html += `<tr><td><a href="/app/project/${encodeURIComponent(r.project)}">${frappe.utils.escape_html(r.project_name || r.project)}</a></td>
                <td><a href="/app/asset-allocation/${encodeURIComponent(r.allocation)}">${r.allocation}</a></td>
                <td>${frappe.datetime.str_to_user(r.delivery_date)}</td>
                <td class="text-right">${flt(r.on_site)}</td><td class="text-right">${money(r.depreciation)}</td></tr>`;
        });
        html += "</tbody></table>";
    } else if (!frm.is_new()) {
        html += `<div class="text-muted small">${__("Not on any project right now.")}</div>`;
    }
    wrapper.html(html);
}

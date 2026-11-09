// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project Budget", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.docstatus < 2) {
            frm.add_custom_button(__("Refresh Actuals"), () => {
                frm.call("refresh_actuals").then(() => {
                    frm.reload_doc();
                    frappe.show_alert({ message: __("Budget figures updated"), indicator: "green" });
                });
            });
        }
        if (frm.doc.project) {
            frm.add_custom_button(__("Project Overview"), () => {
                frappe.set_route("Workspaces", "Project Overview");
            }, __("View"));
            frm.add_custom_button(__("Manpower Cost Summary"), () => {
                frappe.set_route("query-report", "Manpower Cost Summary", { project: frm.doc.project });
            }, __("View"));
            frm.add_custom_button(__("Budget Variance Report"), () => {
                frappe.set_route("query-report", "Project Budget Variance", { project: frm.doc.project });
            }, __("View"));
        }
        set_status_indicator(frm);
        render_budget_dashboard(frm);
    },

    warning_threshold(frm) {
        calculate_totals(frm);
    }
});

frappe.ui.form.on("Project Budget Item", {
    budgeted_amount(frm, cdt, cdn) {
        calculate_row(frm, locals[cdt][cdn]);
        calculate_totals(frm);
    },
    category(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        const duplicate = (frm.doc.budget_items || []).find(
            (r) => r.name !== row.name && r.category && r.category === row.category
        );
        if (duplicate) {
            frappe.msgprint({
                title: __("Duplicate Item Group"),
                indicator: "orange",
                message: __("Item Group {0} is already in row #{1}. Use one line per Item Group.", [
                    row.category.bold(), duplicate.idx
                ])
            });
        }
    },
    budget_items_remove(frm) {
        calculate_totals(frm);
    }
});

function threshold(frm) {
    return flt(frm.doc.warning_threshold) || 90;
}

function status_for(utilization, budget, utilized, limit) {
    if (!budget) return utilized ? "Exceeded" : "Within Budget";
    if (utilization > 100) return "Exceeded";
    if (utilization >= limit) return "Warning";
    return "Within Budget";
}

function calculate_row(frm, row) {
    const budget = flt(row.budgeted_amount);
    const utilized = flt(row.utilized_amount);
    row.variance = budget - utilized;
    row.variance_percentage = budget ? (row.variance / budget) * 100 : 0;
    row.utilization_percentage = budget ? (utilized / budget) * 100 : (utilized ? 100 : 0);
    row.budget_status = status_for(row.utilization_percentage, budget, utilized, threshold(frm));
}

function calculate_totals(frm) {
    let budget = 0, committed = 0, actual = 0, utilized = 0;
    (frm.doc.budget_items || []).forEach((row) => {
        calculate_row(frm, row);
        budget += flt(row.budgeted_amount);
        committed += flt(row.committed_amount);
        actual += flt(row.actual_amount);
        utilized += flt(row.utilized_amount);
    });
    frm.refresh_field("budget_items");

    frm.doc.total_estimated_cost = budget;
    frm.doc.total_committed_cost = committed;
    frm.doc.total_actual_cost = actual;
    frm.doc.total_utilized_cost = utilized;
    frm.doc.variance = budget - utilized;
    frm.doc.variance_percentage = budget ? ((budget - utilized) / budget) * 100 : 0;
    frm.doc.utilization_percentage = budget ? (utilized / budget) * 100 : 0;
    const statuses = (frm.doc.budget_items || []).map((r) => r.budget_status);
    const overall = budget ? status_for(frm.doc.utilization_percentage, budget, utilized, threshold(frm)) : "";
    frm.doc.budget_status = statuses.includes("Exceeded") || overall === "Exceeded" ? "Exceeded"
        : statuses.includes("Warning") || overall === "Warning" ? "Warning" : overall;
    frm.refresh_fields([
        "total_estimated_cost", "total_committed_cost", "total_actual_cost", "total_utilized_cost",
        "variance", "variance_percentage", "utilization_percentage", "budget_status"
    ]);
    set_status_indicator(frm);
    render_budget_dashboard(frm);
}

const STATUS_COLORS = { "Within Budget": "green", "Warning": "orange", "Exceeded": "red" };

function set_status_indicator(frm) {
    if (frm.doc.docstatus === 1 && frm.doc.budget_status) {
        frm.page.set_indicator(__(frm.doc.budget_status), STATUS_COLORS[frm.doc.budget_status] || "gray");
    }
}

function money(value, frm) {
    return format_currency(flt(value), frappe.defaults.get_default("currency"), 0);
}

function render_budget_dashboard(frm) {
    const field = frm.get_field("budget_dashboard");
    if (!field) return;
    const rows = (frm.doc.budget_items || []).filter((r) => r.category);
    if (!rows.length) {
        field.$wrapper.html(`<div class="text-muted small">${__("Add Item Group wise budget lines to see the dashboard.")}</div>`);
        return;
    }

    const limit = threshold(frm);
    const budget = flt(frm.doc.total_estimated_cost);
    const utilized = flt(frm.doc.total_utilized_cost);
    const util_pct = budget ? (utilized / budget) * 100 : 0;
    const exceeded = rows.filter((r) => r.budget_status === "Exceeded");
    const near = rows.filter((r) => r.budget_status === "Warning");

    const card = (label, value, color) => `
        <div class="pb-card">
            <div class="pb-card-label">${label}</div>
            <div class="pb-card-value" style="${color ? `color:${color}` : ""}">${value}</div>
        </div>`;

    const bar_color = (status) =>
        status === "Exceeded" ? "var(--red-500, #e03636)" : status === "Warning" ? "var(--orange-500, #f08c00)" : "var(--green-500, #2f9e44)";

    const sorted = [...rows].sort((a, b) => flt(b.utilization_percentage) - flt(a.utilization_percentage));
    const bars = sorted.map((r) => {
        const pct = flt(r.utilization_percentage);
        const width = Math.min(pct, 100);
        const committed_pct = flt(r.budgeted_amount) ? Math.min((flt(r.committed_amount) / flt(r.budgeted_amount)) * 100, 100) : 0;
        return `
        <div class="pb-row">
            <div class="pb-row-head">
                <span class="pb-row-name">${frappe.utils.escape_html(r.category)}</span>
                <span class="pb-row-figures">
                    ${money(r.utilized_amount)} / ${money(r.budgeted_amount)}
                    <span class="indicator-pill ${STATUS_COLORS[r.budget_status] || "gray"}">${flt(pct, 1)}%</span>
                </span>
            </div>
            <div class="pb-track" title="${__("Committed")}: ${money(r.committed_amount)} | ${__("Actual")}: ${money(r.actual_amount)} | ${__("Manpower")}: ${money(r.manpower_amount)}">
                <div class="pb-fill" style="width:${width}%;background:${bar_color(r.budget_status)}"></div>
                <div class="pb-marker" style="left:${Math.min(limit, 100)}%"></div>
            </div>
            <div class="pb-row-sub text-muted">
                ${__("Committed")} ${money(r.committed_amount)} &middot; ${__("Actual")} ${money(r.actual_amount)} &middot;
                ${flt(r.manpower_amount) ? `${__("Manpower")} ${money(r.manpower_amount)} &middot;` : ""}
                ${__("Balance")} <span style="color:${flt(r.variance) < 0 ? "var(--red-500,#e03636)" : "inherit"}">${money(r.variance)}</span>
            </div>
        </div>`;
    }).join("");

    let alerts = "";
    if (exceeded.length) {
        alerts += `<div class="pb-alert pb-alert-red">${__("Budget exceeded")}: ${exceeded
            .map((r) => `<b>${frappe.utils.escape_html(r.category)}</b> (${money(-flt(r.variance))} ${__("over")})`).join(", ")}</div>`;
    }
    if (near.length) {
        alerts += `<div class="pb-alert pb-alert-orange">${__("Above {0}% used", [limit])}: ${near
            .map((r) => `<b>${frappe.utils.escape_html(r.category)}</b> (${flt(flt(r.utilization_percentage), 1)}%)`).join(", ")}</div>`;
    }
    if (flt(frm.doc.total_manpower_cost)) {
        alerts += `<div class="pb-alert" style="background:var(--subtle-fg,#f4f5f6)">${__("Manpower")}: ${__("Own Staff")} ${money(frm.doc.own_staff_manpower_cost)}
            &middot; ${__("Outsourced")} ${money(frm.doc.outsourced_manpower_cost)}</div>`;
    }
    if (flt(frm.doc.unbudgeted_amount)) {
        alerts += `<div class="pb-alert pb-alert-orange">${__("Unbudgeted spend")}: ${money(frm.doc.unbudgeted_amount)}
            <span class="pb-unbudgeted"></span></div>`;
    }

    field.$wrapper.html(`
        <style>
            .pb-wrap { margin-bottom: 8px; }
            .pb-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 14px; }
            .pb-card { border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 12px; background: var(--card-bg); }
            .pb-card-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .04em; }
            .pb-card-value { font-size: 17px; font-weight: 600; margin-top: 2px; }
            .pb-alert { border-radius: 6px; padding: 8px 12px; margin-bottom: 8px; font-size: 13px; }
            .pb-alert-red { background: var(--red-50, #fff0f0); color: var(--red-700, #a61e1e); }
            .pb-alert-orange { background: var(--orange-50, #fff6e6); color: var(--orange-700, #9c5400); }
            .pb-row { padding: 8px 0; border-bottom: 1px dashed var(--border-color); }
            .pb-row:last-child { border-bottom: none; }
            .pb-row-head { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; font-size: 13px; }
            .pb-row-name { font-weight: 600; }
            .pb-track { position: relative; height: 10px; background: var(--gray-100, #f3f3f3); border-radius: 5px; margin: 6px 0 4px; overflow: hidden; }
            .pb-fill { height: 100%; border-radius: 5px; }
            .pb-marker { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--gray-600, #777); opacity: .6; }
            .pb-row-sub { font-size: 11.5px; }
        </style>
        <div class="pb-wrap">
            <div class="pb-cards">
                ${card(__("Total Budget"), money(budget))}
                ${card(__("Committed"), money(frm.doc.total_committed_cost))}
                ${card(__("Actual"), money(frm.doc.total_actual_cost))}
                ${card(__("Manpower"), money(frm.doc.total_manpower_cost))}
                ${card(__("Utilized"), money(utilized))}
                ${card(__("Balance"), money(frm.doc.variance), flt(frm.doc.variance) < 0 ? "var(--red-500,#e03636)" : "")}
                ${card(__("Utilization"), flt(util_pct, 1) + "%",
                    util_pct > 100 ? "var(--red-500,#e03636)" : util_pct >= limit ? "var(--orange-500,#f08c00)" : "var(--green-500,#2f9e44)")}
            </div>
            ${alerts}
            ${bars}
            ${frm.doc.last_updated_on ? `<div class="text-muted small" style="margin-top:6px">${__("Figures updated on")} ${frappe.datetime.str_to_user(frm.doc.last_updated_on)}</div>` : ""}
        </div>
    `);

    if (flt(frm.doc.unbudgeted_amount) && frm.doc.project && !frm.is_new()) {
        frappe.call({
            method: "altor_project.altor_project.doctype.project_budget.project_budget.get_unbudgeted_spend",
            args: { project: frm.doc.project, budget: frm.doc.name },
            callback(r) {
                const list = (r.message || []).map((g) => `${frappe.utils.escape_html(g.item_group)} (${money(g.utilized)})`);
                if (list.length) field.$wrapper.find(".pb-unbudgeted").html(" — " + list.join(", "));
            }
        });
    }
}

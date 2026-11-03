const state = { company: "", warehouse: "" };

function render(d) {
    const s = d.summary || {};
    let html = `<div class="kpis">
        ${kpi({ label: __("Stock Value"), value: s.stock_value, fmt: "money", icon: "box", color: C.teal, sub: `${num(s.items)} ${__("items in")} ${num(s.warehouses)} ${__("warehouses")}`, route: ["query-report", "Stock Balance"] })}
        ${kpi({ label: __("Stock In · this month"), value: s.stock_in_month, fmt: "money", icon: "down", color: C.green, sub: `${__("Out")} ${money(s.stock_out_month)}`, route: ["query-report", "Stock Ledger"] })}
        ${kpi({ label: __("Pending Receipts"), value: s.pending_receipt_value, fmt: "money", icon: "truck", color: C.blue, sub: s.overdue_receipts ? `<span class="tag down">${num(s.overdue_receipts)} ${__("PO late")}</span> ${__("of")} ${num(s.pending_receipt_pos)}` : `${num(s.pending_receipt_pos)} ${__("purchase orders")}`, route: ["List", "Purchase Order", "List", { status: "To Receive and Bill" }] })}
        ${kpi({ label: __("Issued to Projects"), value: s.issued_to_projects, fmt: "money", icon: "hardhat", color: C.violet, sub: __("This month"), route: ["List", "Stock Entry", "List"] })}
    </div>`;

    const chips = [];
    if (s.below_reorder) chips.push(chip(`<b>${s.below_reorder}</b> ${__("below reorder level")}`, C.orange));
    if (s.negative) chips.push(chip(`<b>${s.negative}</b> ${__("negative stock balances")}`, C.red));
    if (s.overdue_receipts) chips.push(chip(`<b>${s.overdue_receipts}</b> ${__("late purchase receipts")}`, C.red));
    if (s.pending_mr) chips.push(chip(`<b>${s.pending_mr}</b> ${__("material requests to order")}`, C.blue));
    if (flt(s.slow_value)) chips.push(chip(`<b>${money(s.slow_value)}</b> ${__("not moved in 90 days")}`, C.slate));
    if (!chips.length) chips.push(chip(__("Stock levels look healthy"), C.green, true));
    html += `<div class="chips ${a()}">${chips.join("")}</div>`;

    const trend = d.trend || [];
    html += section(__("Movement"));
    html += `<div class="grid">
        ${panel(__("Stock in vs out"), __("Last 14 days, by value"), columns(trend.map((t) => moment(t.date).format("D MMM")), [
            { name: __("In"), color: C.green, values: trend.map((t) => t.in) },
            { name: __("Out"), color: C.orange, values: trend.map((t) => t.out) }
        ], { grouped: true, fmt: money, empty: __("No stock movement in the last 14 days") }), 8)}
        ${panel(__("Value by item group"), "", donut(d.by_group || [], { fmt: money, center_label: __("Stock value"), size: 140 }), 4)}
    </div>`;

    html += section(__("Where it is & where it goes"));
    html += `<div class="grid">
        ${panel(__("Stock value by warehouse"), "", hbars((d.by_warehouse || []).map((w) => ({ ...w, route: ["query-report", "Stock Balance", { warehouse: w.label }] })), { color: C.teal, fmt: money, empty: __("No stock yet") }), 6)}
        ${panel(__("Material issued to projects"), __("This month"), hbars((d.by_project || []).map((p) => ({ ...p, route: ["Form", "Project", p.label] })), { color: C.violet, fmt: money, empty: __("No stock issued to projects this month") }), 6)}
    </div>`;

    const items = (d.top_items || []).map((i) => ({ route: ["Form", "Item", i.item_code], cells: [
        `<b>${esc(i.item_name || i.item_code)}</b><div class="sub">${esc(i.item_code)}</div>`, `${num(i.qty)} <span class="sub">${esc(i.stock_uom || "")}</span>`, num(i.warehouses), money(i.value)] }));
    const reorder = (d.reorder || []).map((r) => ({ route: ["Form", "Item", r.item_code], cells: [
        `<b>${esc(r.item_name || r.item_code)}</b><div class="sub">${esc(r.item_code)}</div>`, esc(r.warehouse), num(r.actual_qty), num(r.projected_qty),
        num(r.reorder_level), `<b style="color:${C.orange}">${num(r.reorder_qty)}</b>`] }));
    const receipts = (d.receipts || []).map((r) => {
        const late = r.schedule_date && r.schedule_date < frappe.datetime.get_today();
        return { route: ["Form", "Purchase Order", r.name], cells: [
            `<b>${esc(r.name)}</b><div class="sub">${esc(r.supplier)}</div>`, esc(r.item_name || r.item_code), `${num(r.pending_qty)} <span class="sub">${esc(r.uom || "")}</span>`,
            `${date(r.schedule_date)} ${late ? pill(__("Late"), "red") : ""}`, money(r.value)] };
    });
    const slow = (d.slow || []).map((r) => ({ route: ["Form", "Item", r.item_code], cells: [
        `<b>${esc(r.item_name || r.item_code)}</b><div class="sub">${esc(r.item_code)}</div>`, num(r.qty), money(r.value)] }));
    const recent = (d.recent || []).map((r) => ({ route: ["Form", "Stock Entry", r.name], cells: [
        `<b>${esc(r.name)}</b>`, pill(__(r.stock_entry_type || r.purpose), "blue"), date(r.posting_date), esc(r.project || "–"),
        money(Math.max(flt(r.total_outgoing_value), flt(r.total_incoming_value)))] }));
    html += section(__("Details"));
    html += `<div class="grid">${panel(__("Items & orders"), "", tabs("st", [
        { key: "top", label: __("Top items by value"), count: items.length, html: table([{ label: __("Item") }, { label: __("Qty"), num: 1 }, { label: __("Warehouses"), num: 1 }, { label: __("Value"), num: 1 }], items, __("No stock yet")) },
        { key: "reorder", label: __("Reorder alerts"), count: reorder.length, html: table([{ label: __("Item") }, { label: __("Warehouse") }, { label: __("Actual"), num: 1 }, { label: __("Projected"), num: 1 }, { label: __("Reorder level"), num: 1 }, { label: __("Order qty"), num: 1 }], reorder, __("Nothing below reorder level")) },
        { key: "receipts", label: __("Pending receipts"), count: receipts.length, html: table([{ label: __("Purchase order") }, { label: __("Item") }, { label: __("Pending"), num: 1 }, { label: __("Expected") }, { label: __("Value"), num: 1 }], receipts, __("No pending receipts")) },
        { key: "slow", label: __("Not moved in 90 days"), count: slow.length, html: table([{ label: __("Item") }, { label: __("Qty"), num: 1 }, { label: __("Value"), num: 1 }], slow, __("All stock moved in the last 90 days")) },
        { key: "recent", label: __("Recent stock entries"), html: table([{ label: __("Stock entry") }, { label: __("Type") }, { label: __("Date") }, { label: __("Project") }, { label: __("Value"), num: 1 }], recent, __("No stock entries yet")) }
    ]), 12)}</div>`;
    return html;
}

function load() {
    load_dashboard({ body: "#body", method: "altor_project.api.dashboard.get_stock_overview",
        filters: () => ({ company: state.company, warehouse: state.warehouse }), render });
}
function load_warehouses() {
    frappe.call({ method: "altor_project.api.dashboard.get_warehouses", args: { company: state.company }, callback(r) {
        fill_select("#fWarehouse", r.message || [], __("All warehouses"), state.warehouse);
    } });
}
frappe.call({ method: "altor_project.api.dashboard.get_filter_options", callback(r) {
    fill_select("#fCompany", (r.message || {}).companies || [], __("All companies"), state.company);
} });
q("#fCompany").addEventListener("change", (e) => { state.company = e.target.value; state.warehouse = ""; load_warehouses(); load(); });
q("#fWarehouse").addEventListener("change", (e) => { state.warehouse = e.target.value; load(); });
q(".btn-refresh").addEventListener("click", load);
load_warehouses();
load();

const state = { company: default_company() };

function change(now, before, lower_is_better) {
    if (!flt(before)) return "";
    const p = ((flt(now) - flt(before)) / Math.abs(flt(before))) * 100;
    const good = lower_is_better ? p <= 0 : p >= 0;
    return `<span class="tag ${good ? "up" : "down"}">${p >= 0 ? "▲" : "▼"} ${Math.abs(p).toFixed(0)}%</span> ${__("vs last month")}`;
}

function render(d) {
    const s = d.summary || {};
    if (d.company && !state.company) { state.company = d.company; const el = q("#fCompany"); if (el) el.value = d.company; }
    q("#accSub").textContent = __("{0} · fiscal year from {1}", [d.company || "", frappe.datetime.str_to_user(s.fy_start)]);
    const net_month = flt(s.income_month) - flt(s.expense_month);

    let html = `<div class="kpis">
        ${kpi({ label: __("Cash & Bank"), value: s.cash, fmt: "money", icon: "bank", color: C.teal, sub: `${__("In")} ${money(s.received_month)} · ${__("Out")} ${money(s.paid_month)} ${__("this month")}`, route: ["query-report", "General Ledger"] })}
        ${kpi({ label: __("Receivables"), value: s.receivable, fmt: "money", icon: "down", color: C.blue, sub: s.receivable_overdue ? `<span class="tag down">${money(s.receivable_overdue)} ${__("overdue")}</span>` : __("Nothing overdue"), route: ["query-report", "Accounts Receivable"] })}
        ${kpi({ label: __("Payables"), value: s.payable, fmt: "money", icon: "up", color: C.orange, sub: s.payable_overdue ? `<span class="tag warn">${money(s.payable_overdue)} ${__("overdue")}</span>` : __("Nothing overdue"), route: ["query-report", "Accounts Payable"] })}
        ${kpi({ label: __("Net Profit · year to date"), value: s.profit_ytd, fmt: "money", icon: "trend", color: flt(s.profit_ytd) >= 0 ? C.green : C.red, sub: `${__("Income")} ${money(s.income_ytd)} · ${__("Expense")} ${money(s.expense_ytd)}`, route: ["query-report", "Profit and Loss Statement"] })}
    </div>`;

    const chips = [];
    if (s.receivable_overdue_count) chips.push(chip(`<b>${s.receivable_overdue_count}</b> ${__("overdue sales invoices")} · ${money(s.receivable_overdue)}`, C.red));
    if (s.payable_overdue_count) chips.push(chip(`<b>${s.payable_overdue_count}</b> ${__("overdue purchase invoices")} · ${money(s.payable_overdue)}`, C.orange));
    if (flt(s.cash) < 0) chips.push(chip(__("Cash & bank balance is negative"), C.red));
    if (net_month < 0) chips.push(chip(__("Expenses are higher than income this month"), C.orange));
    if (!chips.length) chips.push(chip(__("No overdue invoices"), C.green, true));
    html += `<div class="chips ${a()}">${chips.join("")}</div>`;

    const trend = d.trend || [];
    const margin = flt(s.income_month) ? (net_month / flt(s.income_month)) * 100 : 0;
    const month_card = `<div class="feature" style="flex-direction:column;align-items:stretch">
        <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap">${ring(Math.max(margin, 0), margin >= 0 ? C.green : C.red, 120, __("net margin"))}
        <div class="breakdown" style="min-width:160px"><div class="kpi-label">${__("Net this month")}</div>
            <div class="kpi-value" style="color:${net_month >= 0 ? C.green : C.red}">${counter(net_month, "money")}</div></div></div>
        <div class="legend-rows">
            <div><span><i style="background:${C.green}"></i>${__("Income")}</span><b>${money(s.income_month)} ${change(s.income_month, s.income_prev)}</b></div>
            <div><span><i style="background:${C.orange}"></i>${__("Expenses")}</span><b>${money(s.expense_month)} ${change(s.expense_month, s.expense_prev, true)}</b></div>
            <div><span><i style="background:${C.teal}"></i>${__("Collected")}</span><b>${money(s.received_month)}</b></div>
            <div><span><i style="background:${C.violet}"></i>${__("Paid out")}</span><b>${money(s.paid_month)}</b></div>
        </div></div>`;
    html += section(__("Performance"));
    html += `<div class="grid">
        ${panel(__("Income vs expenses"), __("Last 6 months"), columns(trend.map((t) => moment(t.month + "-01").format("MMM YY")), [
            { name: __("Income"), color: C.green, values: trend.map((t) => t.income) },
            { name: __("Expenses"), color: C.orange, values: trend.map((t) => t.expense) }
        ], { grouped: true, fmt: money, empty: __("No income or expense entries yet") }), 8)}
        ${panel(__("This month"), "", month_card, 4)}
    </div>`;

    html += section(__("Receivables & payables"));
    const age_colors = [C.green, C.amber, C.orange, C.red, "#a3262a"];
    html += `<div class="grid">
        ${panel(__("Receivables ageing"), money(s.receivable), hbars((d.receivable_ageing || []).map((x, i) => ({ ...x, color: age_colors[i] })), { fmt: money }), 6)}
        ${panel(__("Payables ageing"), money(s.payable), hbars((d.payable_ageing || []).map((x, i) => ({ ...x, color: age_colors[i] })), { fmt: money }), 6)}
    </div>
    <div class="grid" style="margin-top:12px">
        ${panel(__("Top customers to collect from"), "", hbars((d.top_customers || []).map((c) => ({ ...c, route: ["Form", "Customer", c.label] })), { color: C.blue, fmt: money, empty: __("No outstanding receivables") }), 6)}
        ${panel(__("Top suppliers to pay"), "", hbars((d.top_suppliers || []).map((c) => ({ ...c, route: ["Form", "Supplier", c.label] })), { color: C.orange, fmt: money, empty: __("No outstanding payables") }), 6)}
    </div>`;

    html += section(__("Cash & spending"));
    html += `<div class="grid">
        ${panel(__("Cash & bank accounts"), money(s.cash), hbars((d.cash || []).map((c) => ({ label: c.label, value: c.value, color: flt(c.value) < 0 ? C.red : C.teal, route: ["query-report", "General Ledger", { account: [c.account], company: d.company }] })), { fmt: money, empty: __("No bank or cash accounts with entries") }), 5)}
        ${panel(__("Where the money went"), __("Expenses this month"), donut(d.expense_split || [], { fmt: money, center_label: __("Expenses"), size: 140 }), 7)}
    </div>`;

    const inv_rows = (rows, dt) => rows.map((r) => {
        const days = moment(frappe.datetime.get_today()).diff(moment(r.due_date), "days");
        return { route: ["Form", dt, r.name], cells: [`<b>${esc(r.name)}</b>`, esc(r.party), date(r.due_date),
            pill(__("{0} days late", [days]), days > 60 ? "red" : "orange"), money(r.grand_total), `<b>${money(r.outstanding)}</b>`] };
    });
    const pay_rows = (d.payments || []).map((p) => ({ route: ["Form", "Payment Entry", p.name], cells: [
        `<b>${esc(p.name)}</b>`, pill(__(p.payment_type), p.payment_type === "Receive" ? "green" : p.payment_type === "Pay" ? "orange" : "gray"),
        esc(p.party || "–"), esc(p.mode_of_payment || "–"), date(p.posting_date), money(p.amount)] }));
    const inv_cols = [{ label: __("Invoice") }, { label: __("Party") }, { label: __("Due date") }, { label: __("Late") }, { label: __("Total"), num: 1 }, { label: __("Outstanding"), num: 1 }];
    html += section(__("Details"));
    html += `<div class="grid">${panel(__("Invoices & payments"), "", tabs("acc", [
        { key: "sales", label: __("Overdue sales invoices"), count: (d.overdue_sales || []).length, html: table(inv_cols, inv_rows(d.overdue_sales || [], "Sales Invoice"), __("No overdue sales invoices")) },
        { key: "purchase", label: __("Overdue purchase invoices"), count: (d.overdue_purchases || []).length, html: table(inv_cols, inv_rows(d.overdue_purchases || [], "Purchase Invoice"), __("No overdue purchase invoices")) },
        { key: "payments", label: __("Recent payments"), html: table([{ label: __("Payment") }, { label: __("Type") }, { label: __("Party") }, { label: __("Mode") }, { label: __("Date") }, { label: __("Amount"), num: 1 }], pay_rows, __("No payments yet")) }
    ]), 12)}</div>`;
    return html;
}

function load() {
    load_dashboard({ body: "#body", method: "altor_project.api.dashboard.get_accounts_overview", filters: () => ({ company: state.company }), render });
}
frappe.call({ method: "altor_project.api.dashboard.get_filter_options", callback(r) {
    const o = r.message || {};
    const companies = o.companies || [];
    apply_default_company(state, { ...o, default_company: o.default_company || companies[0] }, load);
    fill_select("#fCompany", companies, null, state.company);
} });
q("#fCompany").addEventListener("change", (e) => { state.company = e.target.value; load(); });
q(".btn-refresh").addEventListener("click", load);
// with a known default company load now; otherwise wait for the company list (apply_default_company)
if (state.company) load();

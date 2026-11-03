const state = { company: default_company(), status: "Open", project: "" };

function render(d) {
    const s = d.summary || {};
    const projects = d.projects || [];
    const util = flt(s.utilization);

    // ---------- headline KPIs
    let html = `<div class="kpis">
        ${kpi({ label: __("Active Projects"), value: s.open, icon: "folder", color: C.blue, sub: `${num(s.completed)} ${__("completed")} · ${num(s.total)} ${__("shown")}`, route: ["List", "Project", "List"] })}
        ${kpi({ label: __("Average Progress"), value: s.avg_progress, fmt: "pct", icon: "trend", color: C.violet, sub: __("Across open projects") })}
        ${kpi({ label: __("Overdue Projects"), value: s.overdue, icon: "clock", color: s.overdue ? C.red : C.green, sub: `${num(s.due_soon)} ${__("due in 30 days")}` })}
        ${kpi({ label: __("Open Tasks"), value: s.open_tasks, icon: "tasks", color: s.overdue_tasks ? C.orange : C.teal, sub: s.overdue_tasks ? `<span class="tag down">${num(s.overdue_tasks)} ${__("overdue")}</span>` : __("Nothing overdue"), route: ["List", "Task", "List"] })}
    </div>`;

    // ---------- alerts
    const chips = [];
    if (s.over_budget) chips.push(chip(`<b>${s.over_budget}</b> ${__("over budget")}`, C.red));
    if (s.at_risk) chips.push(chip(`<b>${s.at_risk}</b> ${__("near budget limit")}`, C.orange));
    if (s.overdue) chips.push(chip(`<b>${s.overdue}</b> ${__("past end date")}`, C.red));
    if (s.without_budget) chips.push(chip(`<b>${s.without_budget}</b> ${__("without a budget")}`, C.orange));
    if (!chips.length) chips.push(chip(__("All projects on track"), C.green, true));
    html += `<div class="chips ${a()}">${chips.join("")}</div>`;

    // ---------- budget health
    const budget = flt(s.budget), utilized = flt(s.utilized), committed = flt(s.committed), manpower = flt(s.manpower);
    const direct = Math.max(utilized - committed - manpower, 0), balance = Math.max(budget - utilized, 0);
    const base = Math.max(budget, utilized, 1);
    const segs = [
        { label: __("Orders (PO & subcontract)"), value: committed, color: C.blue },
        { label: __("Manpower"), value: manpower, color: C.pink },
        { label: __("Direct invoices"), value: direct, color: C.violet },
        { label: utilized > budget ? __("Over budget") : __("Remaining budget"), value: utilized > budget ? utilized - budget : balance, color: utilized > budget ? C.red : "var(--soft)" }
    ];
    const health = budget ? `<div class="feature">
        ${ring(util, util_color(util), 136, __("of budget used"))}
        <div class="breakdown">
            <div class="kpi-label">${__("Total budget")}</div>
            <div class="kpi-value" style="font-size:24px">${counter(budget, "money")}</div>
            <div class="stack">${segs.map((g) => `<div data-w="${(g.value / base) * 100}" style="background:${g.color}" title="${esc(g.label)}: ${esc(money_full(g.value))}"></div>`).join("")}</div>
            <div class="legend-rows">
                ${segs.map((g) => `<div><span><i style="background:${g.color};${g.color === "var(--soft)" ? "border:1px solid var(--line)" : ""}"></i>${esc(g.label)}</span><b>${money(g.value)}</b></div>`).join("")}
                <div><span><i style="background:${C.teal}"></i>${__("Contract value")} · ${__("billed")} ${money(s.billed)}</span><b>${money(s.contract_value)}</b></div>
            </div>
        </div></div>` : empty(__("No submitted Project Budgets yet. Create one from a Project."), "wallet");

    const manpower_html = manpower ? donut([
        { label: __("Own staff"), value: s.manpower_own, color: C.blue },
        { label: __("Outsourced"), value: s.manpower_outsourced, color: C.orange }
    ], { fmt: money, center_label: __("Labour cost"), size: 140 }) +
        `<div class="legend-rows" style="margin-top:12px">
            <div><span><i style="background:${C.pink}"></i>${__("Workers on site today")}</span><b>${num(s.workers_today)}</b></div>
            <div><span><i style="background:${C.violet}"></i>${__("Labour cost this month")}</span><b>${money(s.manpower_this_month)}</b></div></div>`
        : empty(__("No Manpower Entries yet"), "users");

    html += section(__("Budget & cost"));
    html += `<div class="grid">
        ${panel(__("Budget health"), __("Submitted project budgets"), health, 7)}
        ${panel(__("Manpower"), __("Own staff vs outsourced"), manpower_html, 5)}
    </div>`;

    // ---------- per project + status
    const budgeted = projects.filter((p) => p.budget).sort((x, y) => y.utilization - x.utilization).slice(0, 8);
    const bars = hbars(budgeted.map((p) => ({
        label: p.project_name || p.name, value: Math.min(p.actual, p.utilized), ghost: p.utilized, color: util_color(p.utilization),
        text: `${money(p.utilized)} / ${money(p.budget)} · <b style="color:${util_color(p.utilization)}">${pct(p.utilization, 0)}</b>`,
        route: ["Form", "Project Budget", p.budget_name]
    })), { max: Math.max(...budgeted.map((p) => Math.max(p.budget, p.utilized)), 1), empty: __("No submitted Project Budgets yet"),
        legend: `<div class="legend"><span><i style="background:${C.green}"></i>${__("Invoiced")}</span><span><i style="background:${C.green};opacity:.3"></i>${__("Used incl. open orders & manpower")}</span></div>` });
    const status_colors = { Open: C.blue, Completed: C.green, Cancelled: C.slate };
    const status_html = donut(Object.entries(d.status_counts || {}).map(([k, v]) => ({ label: __(k), value: v, color: status_colors[k] })), { center_label: __("Projects") });

    html += `<div class="grid" style="margin-top:12px">
        ${panel(__("Budget used by project"), __("Highest use first"), bars, 7)}
        ${panel(__("Projects by status"), "", status_html, 5)}
    </div>`;

    // ---------- details (tabs)
    const project_rows = projects.map((p) => ({
        route: ["Form", "Project", p.name],
        cells: [
            `<b>${esc(p.project_name || p.name)}</b><div class="sub">${esc(p.name)}${p.customer ? " · " + esc(p.customer) : ""}</div>`,
            pill(__(p.status), { Open: "blue", Completed: "green", Cancelled: "gray" }[p.status]),
            `${mini(p.percent_complete, C.blue)}${pct(p.percent_complete, 0)}`,
            `${date(p.expected_end_date)} ${p.overdue ? pill(__("Overdue"), "red") : p.due_soon ? pill(__("Due soon"), "orange") : ""}`,
            p.budget ? money(p.budget) : "–",
            p.budget ? `${money(p.utilized)}<div class="sub" style="color:${util_color(p.utilization)}">${pct(p.utilization, 0)}</div>` : "–",
            p.manpower ? `${money(p.manpower)}${p.workers_today ? `<div class="sub">${p.workers_today} ${__("today")}</div>` : ""}` : "–",
            p.budget_name ? pill(__(p.budget_status || "Within Budget"), { "Within Budget": "green", Warning: "orange", Exceeded: "red" }[p.budget_status] || "green") : pill(__("No budget"), "gray"),
            `${num((p.tasks || {}).open)}${(p.tasks || {}).overdue ? ` ${pill(`${p.tasks.overdue} ${__("late")}`, "red")}` : ""}`
        ]
    }));
    const groups = d.item_groups || [];
    const group_rows = groups.map((g) => ({
        cells: [
            `<b>${esc(g.item_group)}</b><div class="sub">${g.projects} ${__("project(s)")}</div>`,
            money(g.budget), money(g.committed), money(g.actual), money(g.utilized),
            `<span style="color:${g.balance < 0 ? C.red : "inherit"}">${money(g.balance)}</span>`,
            `${mini(g.utilization, util_color(g.utilization))}<b style="color:${util_color(g.utilization)}">${pct(g.utilization, 0)}</b>`
        ]
    }));
    const alert_rows = (d.alerts || []).map((x) => ({
        route: ["Form", "Project Budget", x.budget_name],
        cells: [esc(x.project), `<b>${esc(x.item_group)}</b>`, money(x.budget), money(x.utilized),
            `<span style="color:${x.balance < 0 ? C.red : "inherit"}">${money(x.balance)}</span>`,
            `<b style="color:${util_color(x.utilization)}">${pct(x.utilization, 0)}</b>`, pill(__(x.status), x.status === "Exceeded" ? "red" : "orange")]
    }));
    const details = tabs("po", [
        { key: "projects", label: __("Projects"), count: projects.length, html: table(
            [{ label: __("Project") }, { label: __("Status") }, { label: __("Progress") }, { label: __("End date") }, { label: __("Budget"), num: 1 },
                { label: __("Used"), num: 1 }, { label: __("Manpower"), num: 1 }, { label: __("Budget status") }, { label: __("Open tasks"), num: 1 }],
            project_rows, __("No projects match the filters")) },
        { key: "groups", label: __("Item group budget"), count: groups.length, html: table(
            [{ label: __("Item group") }, { label: __("Budget"), num: 1 }, { label: __("Committed"), num: 1 }, { label: __("Actual"), num: 1 },
                { label: __("Used"), num: 1 }, { label: __("Balance"), num: 1 }, { label: __("Utilization") }],
            group_rows, __("No item group budgets yet")) },
        { key: "warnings", label: __("Budget warnings"), count: alert_rows.length, html: table(
            [{ label: __("Project") }, { label: __("Item group") }, { label: __("Budget"), num: 1 }, { label: __("Used"), num: 1 },
                { label: __("Balance"), num: 1 }, { label: __("Used %"), num: 1 }, { label: __("Status") }],
            alert_rows, __("All item groups are within budget")) }
    ]);
    html += section(__("Details"));
    html += `<div class="grid">${panel(__("Projects & budgets"), "", details, 12)}</div>`;
    return html;
}

function load() {
    load_dashboard({
        body: "#body",
        method: "altor_project.api.dashboard.get_project_overview",
        filters: () => ({ company: state.company, status: state.status, project: state.project }),
        render
    });
}

frappe.call({
    method: "altor_project.api.dashboard.get_filter_options",
    callback(r) {
        const o = r.message || {};
        apply_default_company(state, o, load);
        fill_select("#fCompany", o.companies || [], __("All companies"), state.company);
        fill_select("#fProject", (o.projects || []).map((p) => ({ value: p.name, label: p.project_name || p.name })), __("All projects"), state.project);
    }
});
q("#fCompany").addEventListener("change", (e) => { state.company = e.target.value; load(); });
q("#fStatus").addEventListener("change", (e) => { state.status = e.target.value; load(); });
q("#fProject").addEventListener("change", (e) => { state.project = e.target.value; load(); });
q(".btn-refresh").addEventListener("click", load);
// with a known default company load now; otherwise wait for the company list (apply_default_company)
if (state.company) load();

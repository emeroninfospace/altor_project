const state = { company: default_company(), department: "" };

function in_days(n) {
    if (n === 0) return pill(__("Today"), "green");
    if (n === 1) return pill(__("Tomorrow"), "blue");
    if (n < 0) return pill(__("Expired"), "red");
    return pill(__("in {0} days", [n]), "gray");
}

function people(items, row, empty_text) {
    if (!items || !items.length) return empty(empty_text, "check");
    return `<div class="table-wrap" style="max-height:340px">${items.map(row).join("")}</div>`;
}

function render(d) {
    const s = d.summary || {};
    q("#hrToday").textContent = __("Today, {0} · headcount, attendance, leave and manpower", [frappe.datetime.str_to_user(frappe.datetime.get_today())]);
    const present = flt(s.present_today) + flt(s.wfh_today);

    let html = `<div class="kpis">
        ${kpi({ label: __("Active Employees"), value: s.total_active, icon: "users", color: C.blue, sub: `${num(s.own_staff)} ${__("own")} · ${num(s.outsourced)} ${__("outsourced")}`, route: ["List", "Employee", "List"] })}
        ${kpi({ label: __("Present Today"), value: present, icon: "check", color: C.green, sub: s.attendance_marked ? `${num(s.wfh_today)} ${__("WFH")} · ${num(s.half_day_today)} ${__("half day")}` : __("Attendance not marked yet"), route: ["List", "Attendance", "List"] })}
        ${kpi({ label: __("On Leave Today"), value: s.on_leave_today, icon: "leave", color: C.orange, sub: `${num(s.pending_leaves)} ${__("requests to approve")}`, route: ["List", "Leave Application", "List"] })}
        ${kpi({ label: __("Workers on Site"), value: s.manpower_today, icon: "hardhat", color: C.pink, sub: `${money(s.manpower_cost_month)} ${__("labour this month")}`, route: ["List", "Manpower Entry", "List"] })}
    </div>`;

    const chips = [];
    const expired = (d.expiring_documents || []).filter((x) => x.days < 0).length;
    if (expired) chips.push(chip(`<b>${expired}</b> ${__("expired passports")}`, C.red));
    if (s.pending_leaves) chips.push(chip(`<b>${s.pending_leaves}</b> ${__("leave requests to approve")}`, C.orange));
    if (s.absent_today) chips.push(chip(`<b>${s.absent_today}</b> ${__("absent today")}`, C.red));
    if (s.joiners_this_month) chips.push(chip(`<b>${s.joiners_this_month}</b> ${__("joined this month")}`, C.blue));
    if (s.exits_this_month) chips.push(chip(`<b>${s.exits_this_month}</b> ${__("left this month")}`, C.slate));
    if (!chips.length) chips.push(chip(__("Nothing needs attention"), C.green, true));
    html += `<div class="chips ${a()}">${chips.join("")}</div>`;

    // attendance
    const trend = d.attendance_trend || [];
    const att = columns(trend.map((t) => moment(t.date).format("ddd D")), [
        { name: __("Present"), color: C.green, values: trend.map((t) => t.present) },
        { name: __("Half day"), color: C.teal, values: trend.map((t) => t.half_day) },
        { name: __("On leave"), color: C.orange, values: trend.map((t) => t.on_leave) },
        { name: __("Absent"), color: C.red, values: trend.map((t) => t.absent) }
    ], { empty: __("No attendance in the last 7 days") });
    const today = donut([
        { label: __("Present"), value: s.present_today, color: C.green },
        { label: __("Work from home"), value: s.wfh_today, color: C.blue },
        { label: __("Half day"), value: s.half_day_today, color: C.teal },
        { label: __("On leave"), value: s.on_leave_today, color: C.orange },
        { label: __("Absent"), value: s.absent_today, color: C.red },
        { label: __("Not marked"), value: s.not_marked_today, color: C.slate }
    ], { center_label: __("Today"), empty: __("Attendance not marked yet today") });
    html += section(__("Attendance"));
    html += `<div class="grid">${panel(__("Last 7 days"), "", att, 7)}${panel(__("Today"), s.checked_in_today ? `${num(s.checked_in_today)} ${__("checked in")}` : "", today, 5)}</div>`;

    // workforce
    html += section(__("Workforce"));
    html += `<div class="grid">
        ${panel(__("By department"), "", hbars((d.by_department || []).slice(0, 8), { color: C.blue }), 4)}
        ${panel(__("Gender"), "", donut(d.by_gender || [], { center_label: __("Employees"), size: 130 }), 4)}
        ${panel(__("Employment type"), "", donut(d.by_employment_type || [], { center_label: __("Employees"), size: 130 }), 4)}
    </div>`;
    const mp_tabs = tabs("mp", [
        { key: "project", label: __("By project"), html: hbars(d.manpower_by_project || [], { color: C.pink, fmt: money, empty: __("No Manpower Entries this month") }) },
        { key: "agency", label: __("By agency"), html: hbars(d.manpower_cost_by_agency || [], { color: C.orange, fmt: money, empty: __("No agency cost this month") }) }
    ]);
    html += `<div class="grid" style="margin-top:12px">
        ${panel(__("Outsourced manpower"), `${num(s.outsourced)} ${__("workers")}`, hbars(d.by_agency || [], { color: C.orange, fmt: (v) => `${num(v)} ${__("workers")}`, empty: __("No outsourced workers. Tick Outsourced Manpower on the Employee.") }), 5)}
        ${panel(__("Labour cost this month"), money(s.manpower_cost_month), mp_tabs, 7)}
    </div>`;

    // people
    const leave_row = (l, i) => `<div class="list-row link" data-route='${esc(JSON.stringify(["Form", "Leave Application", l.name]))}'><span class="who">${avatar(l.employee_name, i)}<span><b>${esc(l.employee_name)}</b><div class="sub">${esc(l.leave_type)}${l.total_leave_days ? ` · ${flt(l.total_leave_days)} ${__("day(s)")}` : ""}</div></span></span><span class="sub">${date(l.from_date)} – ${date(l.to_date)}</span></div>`;
    const event_row = (key) => (x, i) => `<div class="list-row link" data-route='${esc(JSON.stringify(["Form", "Employee", x.employee]))}'><span class="who">${avatar(x.employee_name, i)}<span><b>${esc(x.employee_name)}</b><div class="sub">${esc(key(x))}</div></span></span><span>${date(x.date || x.date_of_joining)} ${x.days != null ? in_days(x.days) : ""}</span></div>`;
    const ppl = tabs("people", [
        { key: "leave", label: __("On leave today"), count: (d.leaves_today || []).length, html: people(d.leaves_today, leave_row, __("No one is on leave today")) },
        { key: "pending", label: __("Leave to approve"), count: (d.pending_leaves || []).length, html: people(d.pending_leaves, leave_row, __("No pending leave applications")) },
        { key: "bday", label: __("Birthdays"), count: (d.birthdays || []).length, html: people(d.birthdays, event_row((x) => x.department || ""), __("No birthdays in the next 30 days")) },
        { key: "anniv", label: __("Anniversaries"), count: (d.anniversaries || []).length, html: people(d.anniversaries, event_row((x) => `${x.years} ${__("year(s)")}`), __("No work anniversaries in the next 30 days")) },
        { key: "docs", label: __("Passports expiring"), count: (d.expiring_documents || []).length, html: people(d.expiring_documents, event_row((x) => `${x.document} ${x.number || ""}`), __("No passports expiring in the next 60 days")) },
        { key: "new", label: __("New joiners"), count: (d.new_joiners || []).length, html: people(d.new_joiners, event_row((x) => [x.designation, x.department].filter(Boolean).join(" · ")), __("No new joiners this month")) }
    ]);
    html += section(__("People"));
    html += `<div class="grid">${panel(__("People & events"), "", ppl, 12)}</div>`;
    return html;
}

function load() {
    load_dashboard({
        body: "#body",
        method: "altor_project.api.dashboard.get_hr_overview",
        filters: () => ({ company: state.company, department: state.department }),
        render
    });
}

frappe.call({
    method: "altor_project.api.dashboard.get_filter_options",
    callback(r) {
        const o = r.message || {};
        apply_default_company(state, o, load);
        fill_select("#fCompany", o.companies || [], __("All companies"), state.company);
        fill_select("#fDepartment", o.departments || [], __("All departments"), state.department);
    }
});
q("#fCompany").addEventListener("change", (e) => { state.company = e.target.value; load(); });
q("#fDepartment").addEventListener("change", (e) => { state.department = e.target.value; load(); });
q(".btn-refresh").addEventListener("click", load);
// with a known default company load now; otherwise wait for the company list (apply_default_company)
if (state.company) load();

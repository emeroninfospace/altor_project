/* Altor dashboard kit: helpers shared by every dashboard block (runs inside the block's shadow root). */
const C = { blue: "#2f7ff0", green: "#23a15b", orange: "#ef8a17", red: "#e5484d", violet: "#7c5cff", teal: "#12a4a4", pink: "#d6407a", slate: "#8692a0", amber: "#f5b301", indigo: "#4f5bd5" };
const PALETTE = [C.blue, C.green, C.orange, C.violet, C.teal, C.pink, C.amber, C.red, C.indigo, C.slate];
const REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const KIT = { currency: null };

function esc(v) { return frappe.utils.escape_html(v == null ? "" : String(v)); }
function q(sel) { return root_element.querySelector(sel); }
function qa(sel) { return Array.from(root_element.querySelectorAll(sel)); }

function currency_code() { return KIT.currency || frappe.defaults.get_default("currency") || ""; }
function compact(v) {
    const n = flt(v);
    if (Math.abs(n) < 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
    return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: Math.abs(n) < 100000 ? 1 : 2 }).format(n);
}
function money(v) { return `${currency_code()} ${compact(v)}`; }
function money_full(v) { return `${currency_code()} ${flt(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`; }
function num(v) { return flt(v).toLocaleString(undefined, { maximumFractionDigits: 0 }); }
function pct(v, d) { return `${flt(v).toFixed(d == null ? 1 : d)}%`; }
function date(d) { return d ? esc(frappe.datetime.str_to_user(d)) : "–"; }
function util_color(p) { return p > 100 ? C.red : p >= 90 ? C.orange : C.green; }
function initials(name) { return esc(String(name || "?").replace(/^DEMO\s+/, "").split(/\s+/).slice(0, 2).map((s) => s[0]).join("").toUpperCase()); }
function avatar(name, i) { return `<span class="avatar" style="background:${PALETTE[(i || 0) % PALETTE.length]}">${initials(name)}</span>`; }

const ICONS = {
    folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    alert: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    trend: '<path d="m3 17 6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    wallet: '<path d="M20 7H5a2 2 0 0 1 0-4h13v4"/><path d="M3 5v14a2 2 0 0 0 2 2h15V7"/><path d="M16 14h.01"/>',
    coins: '<circle cx="8" cy="8" r="6"/><path d="M18.1 10.4A6 6 0 1 1 10.3 18"/><path d="M7 6h1v4"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    tasks: '<path d="M9 11l3 3 8-8"/><path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/>',
    hardhat: '<path d="M2 18h20M4 18v-3a8 8 0 0 1 16 0v3"/><path d="M10 7V5h4v2"/>',
    box: '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5M12 13v8"/>',
    warehouse: '<path d="M3 21V8l9-5 9 5v13"/><path d="M7 21v-8h10v8M7 17h10"/>',
    truck: '<path d="M3 6h11v10H3zM14 9h4l3 3v4h-7z"/><circle cx="7" cy="18" r="2"/><circle cx="17" cy="18" r="2"/>',
    down: '<path d="M12 5v14M5 12l7 7 7-7"/>',
    up: '<path d="M12 19V5M5 12l7-7 7 7"/>',
    receipt: '<path d="M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2z"/><path d="M9 8h6M9 12h6"/>',
    bank: '<path d="M3 10h18L12 4zM5 10v8M9 10v8M15 10v8M19 10v8M3 20h18"/>',
    calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8"/><path d="M21 3v5h-5"/>',
    chart: '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>',
    pie: '<path d="M21 12A9 9 0 1 1 12 3v9z"/><path d="M15 3.5A9 9 0 0 1 20.5 9H15z"/>',
    leave: '<path d="M8 2v4M16 2v4"/><rect x="3" y="4" width="18" height="18" rx="2"/><path d="m9 15 2 2 4-4"/>',
    gift: '<rect x="3" y="8" width="18" height="4"/><path d="M12 8v13M5 12v9h14v-9"/><path d="M12 8a3 3 0 1 1-3-3c2 0 3 3 3 3zM12 8a3 3 0 1 0 3-3c-2 0-3 3-3 3z"/>',
    id: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M15 9h3M15 13h3M6 16h6"/>',
    cart: '<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M2 3h3l2.7 12.4a2 2 0 0 0 2 1.6h7.6a2 2 0 0 0 2-1.5L21 8H6"/>',
    layers: '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5M2 12l10 5 10-5"/>'
};
function icon(name, size) {
    size = size || 18;
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ICONS.chart}</svg>`;
}

let ANIM_I = 0;
function a() { return `anim" style="--i:${ANIM_I++}`; } // usage: class="panel ${a()}"

/* value: number; fmt: "money" | "num" | "pct"; data-count drives the count-up animation */
function counter(value, fmt) {
    const text = fmt === "money" ? money(value) : fmt === "pct" ? pct(value) : num(value);
    const title = fmt === "money" ? money_full(value) : text;
    return `<span data-count="${flt(value)}" data-fmt="${fmt || "num"}" title="${esc(title)}">${text}</span>`;
}

function kpi(o) {
    const route = o.route ? ` data-route='${esc(JSON.stringify(o.route))}'` : "";
    return `<div class="kpi ${o.route ? "link" : ""} ${a()};--accent:${o.color || C.blue}"${route}>
        <div class="kpi-icon">${icon(o.icon || "chart")}</div>
        <div class="kpi-body">
            <div class="kpi-label">${o.label}</div>
            <div class="kpi-value">${o.html != null ? o.html : counter(o.value, o.fmt)}${o.unit ? `<small>${o.unit}</small>` : ""}</div>
            ${o.sub ? `<div class="kpi-sub">${o.sub}</div>` : ""}
        </div></div>`;
}

function chip(text, color, ok) {
    return `<span class="chip ${ok ? "ok" : ""}" style="--c:${color}"><span class="dot"></span>${text}</span>`;
}

function section(title) { return `<div class="section ${a()}">${title}</div>`; }

function panel(title, sub, body, span, extra) {
    return `<div class="panel span-${span || 6} ${a()}" ${extra || ""}><div class="panel-head"><h3>${title}</h3>${sub ? `<span>${sub}</span>` : ""}</div>${body}</div>`;
}

function empty(text, ic) { return `<div class="empty">${icon(ic || "chart", 26)}${esc(text)}</div>`; }

function ring(value, color, size, label) {
    size = size || 132;
    const r = size / 2 - 11, c = 2 * Math.PI * r, p = Math.max(0, Math.min(flt(value), 100));
    return `<div class="ring" style="width:${size}px;height:${size}px">
        <svg width="${size}" height="${size}"><circle r="${r}" cx="${size / 2}" cy="${size / 2}" fill="none" stroke="var(--soft)" stroke-width="11"/>
        <circle r="${r}" cx="${size / 2}" cy="${size / 2}" fill="none" stroke="${color}" stroke-width="11" stroke-linecap="round"
            stroke-dasharray="0 ${c}" data-dash="${(p / 100) * c} ${c}" style="transition:stroke-dasharray 1.2s cubic-bezier(.2,.8,.2,1)"/></svg>
        <div class="ring-center"><div><b>${counter(value, "pct")}</b><span>${label || ""}</span></div></div></div>`;
}

function donut(items, o) {
    o = o || {};
    const size = o.size || 150, r = size / 2 - 13, c = 2 * Math.PI * r;
    items = items.filter((i) => flt(i.value) > 0);
    const total = items.reduce((s, i) => s + flt(i.value), 0);
    const fmt = o.fmt || ((v) => num(v));
    let offset = 0;
    const arcs = items.map((it, idx) => {
        const len = total ? (flt(it.value) / total) * c : 0;
        const color = it.color || PALETTE[idx % PALETTE.length];
        const gap = items.length > 1 ? Math.min(2, len / 4) : 0;
        const arc = `<circle class="arc" r="${r}" cx="${size / 2}" cy="${size / 2}" fill="none" stroke="${color}" stroke-width="16"
            stroke-dasharray="0 ${c}" data-dash="${Math.max(len - gap, 0)} ${c}" stroke-dashoffset="${-offset}"><title>${esc(it.label)}: ${esc(fmt(it.value))}</title></circle>`;
        offset += len;
        return arc;
    }).join("");
    if (!total) return empty(o.empty || __("No data yet"), "pie");
    const list = items.map((it, idx) => `<div><span><i style="background:${it.color || PALETTE[idx % PALETTE.length]}"></i>${esc(it.label)}</span>
        <b>${esc(fmt(it.value))} <span class="sub">${pct((flt(it.value) / total) * 100, 0)}</span></b></div>`).join("");
    return `<div class="donut"><div class="donut-wrap"><svg width="${size}" height="${size}"><circle r="${r}" cx="${size / 2}" cy="${size / 2}" fill="none" stroke="var(--soft)" stroke-width="16"/>${arcs}</svg>
        <div class="ring-center"><div><b style="font-size:${o.fmt ? 15 : 22}px">${esc(o.center != null ? o.center : fmt(total))}</b><span>${esc(o.center_label || __("Total"))}</span></div></div></div>
        <div class="donut-list">${list}</div></div>`;
}

/* items: [{label, value, color?, ghost?, route?, sub?}] */
function hbars(items, o) {
    o = o || {};
    if (!items.length) return empty(o.empty || __("No data yet"));
    const max = o.max || Math.max(...items.map((i) => Math.max(flt(i.value), flt(i.ghost))), 1);
    const fmt = o.fmt || num;
    return items.map((it, idx) => {
        const color = it.color || o.color || PALETTE[idx % PALETTE.length];
        const route = it.route ? ` data-route='${esc(JSON.stringify(it.route))}'` : "";
        return `<div class="hbar ${it.route ? "link" : ""}"${route}><div class="hbar-head"><span class="hbar-name" title="${esc(it.label)}">${esc(it.label)}</span>
            <span class="hbar-val">${it.text != null ? it.text : esc(fmt(it.value))}</span></div>
            <div class="track">${it.ghost != null ? `<div class="fill ghost" data-w="${Math.min((flt(it.ghost) / max) * 100, 100)}" style="background:${color}"></div>` : ""}
            <div class="fill" data-w="${Math.min((flt(it.value) / max) * 100, 100)}" style="background:${color}"></div></div></div>`;
    }).join("") + (o.legend || "");
}

/* labels: [..]; series: [{name, color, values: [..]}]; stacked columns */
function columns(labels, series, o) {
    o = o || {};
    const totals = labels.map((_, i) => series.reduce((s, se) => s + Math.max(flt(se.values[i]), 0), 0));
    const max = Math.max(...totals, 1);
    if (!totals.some((t) => t > 0)) return empty(o.empty || __("No data yet"));
    const fmt = o.fmt || num;
    const cols = labels.map((label, i) => {
        if (o.grouped) {
            return `<div class="col">${series.map((se) => `<div class="col-bar" data-h="${(Math.max(flt(se.values[i]), 0) / Math.max(...series.flatMap((s) => s.values.map(flt)), 1)) * 100}"
                title="${esc(label)} · ${esc(se.name)}: ${esc(fmt(se.values[i]))}"><div style="height:100%;background:${se.color}"></div></div>`).join("")}</div>`;
        }
        const segs = series.map((se) => {
            const v = Math.max(flt(se.values[i]), 0);
            return v ? `<div style="height:${totals[i] ? (v / totals[i]) * 100 : 0}%;background:${se.color}" title="${esc(label)} · ${esc(se.name)}: ${esc(fmt(v))}"></div>` : "";
        }).join("");
        return `<div class="col"><div class="col-bar" data-h="${(totals[i] / max) * 100}">${segs}</div></div>`;
    }).join("");
    const legend = series.map((se) => `<span><i style="background:${se.color}"></i>${esc(se.name)}</span>`).join("");
    return `<div class="cols">${cols}</div><div class="col-labels">${labels.map((l) => `<span>${esc(l)}</span>`).join("")}</div><div class="legend">${legend}</div>`;
}

function pill(text, color) { return `<span class="pill ${color || "gray"}">${esc(text)}</span>`; }
function mini(p, color) { return `<span class="mini"><span data-w="${Math.min(flt(p), 100)}" style="background:${color || C.blue}"></span></span>`; }

/* tabs: [{key, label, count?, html}] */
function tabs(id, list) {
    return `<div class="tabs" data-tabs="${id}">${list.map((t, i) => `<button type="button" class="tab ${i ? "" : "active"}" data-tab="${t.key}">${esc(t.label)}${t.count != null ? `<span class="count">${t.count}</span>` : ""}</button>`).join("")}</div>
        ${list.map((t, i) => `<div class="tab-pane ${i ? "" : "active"}" data-pane="${id}:${t.key}">${t.html}</div>`).join("")}`;
}

/* columns: [{label, num?}]; rows: [{cells:[..html], route?}] */
function table(cols, rows, empty_text) {
    if (!rows.length) return empty(empty_text || __("Nothing to show"), "check");
    return `<div class="table-wrap"><table class="t"><thead><tr>${cols.map((c) => `<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("")}</tr></thead>
        <tbody>${rows.map((r) => `<tr class="${r.route ? "link" : ""}" ${r.route ? `data-route='${esc(JSON.stringify(r.route))}'` : ""}>${r.cells.map((c, i) => `<td class="${cols[i] && cols[i].num ? "num" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function skeleton() {
    return `<div class="kpis">${'<div class="skel"></div>'.repeat(4)}</div><div class="grid" style="margin-top:12px">
        <div class="skel tall span-7"></div><div class="skel tall span-5"></div></div>`;
}

function fill_select(sel, values, placeholder, current) {
    const el = q(sel);
    if (!el) return;
    el.innerHTML = (placeholder != null ? `<option value="">${esc(placeholder)}</option>` : "") + values.map((v) => {
        const value = typeof v === "string" ? v : v.value;
        const label = typeof v === "string" ? v : v.label;
        return `<option value="${esc(value)}" ${value === current ? "selected" : ""}>${esc(label)}</option>`;
    }).join("");
}

/* run after innerHTML: count-ups, bars, rings, routes, tabs */
function animate(container) {
    const fmts = { money, pct: (v) => pct(v), num };
    container.querySelectorAll("[data-count]").forEach((el) => {
        const target = flt(el.dataset.count), f = fmts[el.dataset.fmt] || num;
        if (REDUCED || !target) { el.textContent = f(target); return; }
        const start = performance.now(), dur = 900;
        const step = (now) => {
            const t = Math.min((now - start) / dur, 1), e = 1 - Math.pow(1 - t, 3);
            el.textContent = f(target * e);
            if (t < 1) requestAnimationFrame(step); else el.textContent = f(target);
        };
        requestAnimationFrame(step);
    });
    requestAnimationFrame(() => requestAnimationFrame(() => {
        container.querySelectorAll("[data-w]").forEach((el) => { el.style.width = el.dataset.w + "%"; });
        container.querySelectorAll("[data-h]").forEach((el) => { el.style.height = el.dataset.h + "%"; });
        container.querySelectorAll("[data-dash]").forEach((el) => { el.setAttribute("stroke-dasharray", el.dataset.dash); });
    }));
    container.querySelectorAll("[data-route]").forEach((el) => {
        el.addEventListener("click", () => frappe.set_route(...JSON.parse(el.dataset.route)));
    });
    container.querySelectorAll("[data-tabs]").forEach((bar) => {
        const id = bar.dataset.tabs;
        bar.querySelectorAll(".tab").forEach((btn) => btn.addEventListener("click", () => {
            bar.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === btn));
            container.querySelectorAll(`[data-pane^="${id}:"]`).forEach((p) => {
                const on = p.dataset.pane === `${id}:${btn.dataset.tab}`;
                p.classList.toggle("active", on);
                if (on) p.querySelectorAll("[data-w]").forEach((el) => { el.style.width = el.dataset.w + "%"; });
            });
        }));
    });
}

/* standard loader: shows skeleton, calls method, renders, animates */
function load_dashboard(o) {
    const body = q(o.body);
    const btn = q(".btn-refresh");
    if (!body.dataset.loaded) body.innerHTML = skeleton();
    if (btn) btn.classList.add("spin");
    frappe.call({
        method: o.method,
        args: { filters: o.filters() },
        callback(r) {
            const data = r.message || {};
            KIT.currency = data.currency || KIT.currency;
            ANIM_I = 0;
            body.innerHTML = o.render(data);
            body.dataset.loaded = 1;
            animate(body);
            const up = q(".updated");
            if (up) up.textContent = __("Updated {0}", [moment().format("HH:mm")]);
        },
        error() { body.innerHTML = empty(__("Could not load the dashboard. Check your permissions or try again.")); },
        always() { if (btn) btn.classList.remove("spin"); }
    });
}

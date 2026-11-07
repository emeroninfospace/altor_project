# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Data for the Project Overview and HR dashboards (Custom HTML Blocks)."""

import json

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_first_day, get_last_day, getdate, nowdate


def _parse(filters):
	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except ValueError:
			filters = {}
	return frappe._dict(filters or {})


def _doctype_exists(doctype):
	return bool(frappe.db.exists("DocType", doctype))


# ---------------------------------------------------------------------------
# Project Overview
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_filter_options():
	companies = frappe.get_list("Company", pluck="name", order_by="name")
	default = _company({})
	return {
		"companies": companies,
		"default_company": default
		if default in companies
		else (companies[0] if len(companies) == 1 else None),
		"projects": frappe.get_list(
			"Project", fields=["name", "project_name"], order_by="modified desc", limit_page_length=500
		),
		"departments": frappe.get_list("Department", pluck="name", order_by="name", limit_page_length=500)
		if _doctype_exists("Department")
		else [],
	}


@frappe.whitelist()
def get_project_overview(filters=None):
	filters = _parse(filters)
	frappe.has_permission("Project", "read", throw=True)
	today = getdate(nowdate())

	project_filters = {}
	if filters.company:
		project_filters["company"] = filters.company
	if filters.project:
		project_filters["name"] = filters.project
	if filters.status:
		project_filters["status"] = filters.status

	projects = frappe.get_list(
		"Project",
		filters=project_filters,
		fields=[
			"name",
			"project_name",
			"status",
			"percent_complete",
			"expected_start_date",
			"expected_end_date",
			"customer",
			"company",
			"quotation",
			"total_sales_amount",
			"total_billed_amount",
		],
		order_by="expected_end_date asc",
		limit_page_length=0,
	)
	names = [p.name for p in projects]

	# Contract value: linked quotation, else sales orders on the project
	quotations = [p.quotation for p in projects if p.get("quotation")]
	quotation_value = {}
	if quotations:
		for q in frappe.get_all(
			"Quotation", filters={"name": ["in", quotations]}, fields=["name", "base_net_total"]
		):
			quotation_value[q.name] = flt(q.base_net_total)

	# Latest submitted budget per project
	budgets = {}
	budget_lines = []
	if names:
		for b in frappe.get_all(
			"Project Budget",
			filters={"project": ["in", names], "docstatus": 1},
			fields=[
				"name",
				"project",
				"total_estimated_cost",
				"total_committed_cost",
				"total_actual_cost",
				"total_utilized_cost",
				"variance",
				"utilization_percentage",
				"unbudgeted_amount",
				"budget_status",
				"last_updated_on",
			],
			order_by="posting_date desc, creation desc",
		):
			budgets.setdefault(b.project, b)
		if budgets:
			budget_lines = frappe.get_all(
				"Project Budget Item",
				filters={
					"parenttype": "Project Budget",
					"parent": ["in", [b.name for b in budgets.values()]],
				},
				fields=[
					"parent",
					"category",
					"budgeted_amount",
					"committed_amount",
					"actual_amount",
					"utilized_amount",
					"variance",
					"utilization_percentage",
					"budget_status",
				],
			)

	# Tasks: one grouped query instead of loading every task
	task_stats = {}
	if names:
		for t in frappe.db.sql(
			"""
			SELECT project,
				COUNT(*) AS total,
				SUM(status = 'Completed') AS completed,
				SUM(status NOT IN ('Completed', 'Cancelled')) AS open,
				SUM(status NOT IN ('Completed', 'Cancelled') AND exp_end_date < %(today)s) AS overdue
			FROM `tabTask`
			WHERE project IN %(projects)s
			GROUP BY project
			""",
			{"projects": tuple(names), "today": today},
			as_dict=True,
		):
			task_stats[t.project] = {k: int(t[k] or 0) for k in ("total", "completed", "open", "overdue")}

	# Manpower (own staff + outsourced) per project
	manpower = {}
	if names:
		month_start = get_first_day(today)
		for m in frappe.db.sql(
			"""
			SELECT me.project,
				SUM(CASE WHEN d.worker_type = 'Outsourced' THEN 0 ELSE d.amount END) AS own,
				SUM(CASE WHEN d.worker_type = 'Outsourced' THEN d.amount ELSE 0 END) AS outsourced,
				SUM(CASE WHEN me.posting_date >= %(month_start)s THEN d.amount ELSE 0 END) AS this_month,
				SUM(CASE WHEN me.posting_date = %(today)s THEN d.no_of_workers ELSE 0 END) AS workers_today
			FROM `tabManpower Entry Detail` d
			INNER JOIN `tabManpower Entry` me ON me.name = d.parent
			WHERE me.docstatus = 1 AND me.project IN %(projects)s
			GROUP BY me.project
			""",
			{"projects": tuple(names), "today": today, "month_start": month_start},
			as_dict=True,
		):
			manpower[m.project] = m

	summary = frappe._dict(
		total=len(projects),
		open=0,
		completed=0,
		cancelled=0,
		overdue=0,
		due_soon=0,
		avg_progress=0,
		contract_value=0,
		billed=0,
		budget=0,
		committed=0,
		actual=0,
		utilized=0,
		over_budget=0,
		at_risk=0,
		without_budget=0,
		open_tasks=0,
		overdue_tasks=0,
		manpower=0,
		manpower_own=0,
		manpower_outsourced=0,
		manpower_this_month=0,
		workers_today=0,
	)
	status_counts = {}
	rows = []
	progress_sum, progress_n = 0, 0
	for p in projects:
		status_counts[p.status or _("Not Set")] = status_counts.get(p.status or _("Not Set"), 0) + 1
		end = getdate(p.expected_end_date) if p.expected_end_date else None
		is_open = p.status == "Open"
		overdue = bool(is_open and end and end < today)
		due_soon = bool(is_open and end and today <= end <= add_days(today, 30))
		if p.status == "Open":
			summary.open += 1
			progress_sum += flt(p.percent_complete)
			progress_n += 1
		elif p.status == "Completed":
			summary.completed += 1
		elif p.status == "Cancelled":
			summary.cancelled += 1
		summary.overdue += overdue
		summary.due_soon += due_soon

		contract = quotation_value.get(p.get("quotation")) or flt(p.total_sales_amount)
		b = budgets.get(p.name)
		t = task_stats.get(p.name, {})
		summary.contract_value += contract
		summary.billed += flt(p.total_billed_amount)
		mp = manpower.get(p.name) or {}
		mp_total = flt(mp.get("own")) + flt(mp.get("outsourced"))
		summary.manpower += mp_total
		summary.manpower_own += flt(mp.get("own"))
		summary.manpower_outsourced += flt(mp.get("outsourced"))
		summary.manpower_this_month += flt(mp.get("this_month"))
		summary.workers_today += int(mp.get("workers_today") or 0)
		summary.open_tasks += t.get("open", 0)
		summary.overdue_tasks += t.get("overdue", 0)
		if b:
			summary.budget += flt(b.total_estimated_cost)
			summary.committed += flt(b.total_committed_cost)
			summary.actual += flt(b.total_actual_cost)
			summary.utilized += flt(b.total_utilized_cost)
			summary.over_budget += b.budget_status == "Exceeded"
			summary.at_risk += b.budget_status == "Warning"
		elif p.status == "Open":
			summary.without_budget += 1

		rows.append(
			{
				"name": p.name,
				"project_name": p.project_name,
				"status": p.status,
				"customer": p.customer,
				"percent_complete": flt(p.percent_complete),
				"expected_end_date": p.expected_end_date,
				"overdue": overdue,
				"due_soon": due_soon,
				"contract_value": contract,
				"billed": flt(p.total_billed_amount),
				"budget_name": b.name if b else None,
				"budget": flt(b.total_estimated_cost) if b else 0,
				"committed": flt(b.total_committed_cost) if b else 0,
				"actual": flt(b.total_actual_cost) if b else 0,
				"utilized": flt(b.total_utilized_cost) if b else 0,
				"balance": flt(b.variance) if b else 0,
				"utilization": flt(b.utilization_percentage) if b else 0,
				"unbudgeted": flt(b.unbudgeted_amount) if b else 0,
				"budget_status": b.budget_status if b else "",
				"tasks": t,
				"manpower": mp_total,
				"manpower_outsourced": flt(mp.get("outsourced")),
				"workers_today": int(mp.get("workers_today") or 0),
			}
		)
	summary.avg_progress = round(progress_sum / progress_n, 1) if progress_n else 0
	summary.utilization = round(summary.utilized / summary.budget * 100, 1) if summary.budget else 0
	summary.balance = summary.budget - summary.utilized

	# Item group breakdown across the selected projects
	budget_to_project = {b.name: b.project for b in budgets.values()}
	groups, alerts = {}, []
	for line in budget_lines:
		g = groups.setdefault(
			line.category,
			{
				"item_group": line.category,
				"budget": 0,
				"committed": 0,
				"actual": 0,
				"utilized": 0,
				"projects": 0,
			},
		)
		g["budget"] += flt(line.budgeted_amount)
		g["committed"] += flt(line.committed_amount)
		g["actual"] += flt(line.actual_amount)
		g["utilized"] += flt(line.utilized_amount)
		g["projects"] += 1
		if line.budget_status in ("Exceeded", "Warning"):
			alerts.append(
				{
					"project": budget_to_project.get(line.parent),
					"budget_name": line.parent,
					"item_group": line.category,
					"budget": flt(line.budgeted_amount),
					"utilized": flt(line.utilized_amount),
					"balance": flt(line.variance),
					"utilization": flt(line.utilization_percentage),
					"status": line.budget_status,
				}
			)
	for g in groups.values():
		g["balance"] = g["budget"] - g["utilized"]
		g["utilization"] = (
			round(g["utilized"] / g["budget"] * 100, 1) if g["budget"] else (100 if g["utilized"] else 0)
		)
	alerts.sort(key=lambda a: (a["status"] != "Exceeded", -a["utilization"]))

	return {
		"summary": summary,
		"status_counts": status_counts,
		"projects": rows,
		"item_groups": sorted(groups.values(), key=lambda g: -g["budget"]),
		"alerts": alerts[:50],
		"currency": frappe.get_cached_value("Company", filters.company, "default_currency")
		if filters.company
		else frappe.defaults.get_global_default("currency"),
	}


# ---------------------------------------------------------------------------
# HR Dashboard
# ---------------------------------------------------------------------------


def _next_occurrence(d, today):
	"""Next anniversary of date `d` on/after today (Feb 29 -> Feb 28)."""
	for year in (today.year, today.year + 1):
		try:
			nxt = d.replace(year=year)
		except ValueError:
			nxt = d.replace(year=year, day=28)
		if nxt >= today:
			return nxt
	return None


@frappe.whitelist()
def get_hr_overview(filters=None):
	filters = _parse(filters)
	frappe.has_permission("Employee", "read", throw=True)
	today = getdate(nowdate())
	month_start, month_end = get_first_day(today), get_last_day(today)

	emp_filters = {}
	if filters.company:
		emp_filters["company"] = filters.company
	if filters.department:
		emp_filters["department"] = filters.department

	meta = frappe.get_meta("Employee")
	fields = [
		"name",
		"employee_name",
		"status",
		"department",
		"designation",
		"gender",
		"date_of_joining",
		"relieving_date",
		"date_of_birth",
		"branch",
		"employment_type",
		"image",
		"custom_is_outsourced",
		"custom_manpower_supplier",
	]
	fields = [f for f in fields if f in ("name",) or meta.has_field(f)]
	has_passport = meta.has_field("valid_upto")
	if has_passport:
		fields += ["passport_number", "valid_upto"]

	employees = frappe.get_list("Employee", filters=emp_filters, fields=fields, limit_page_length=0)
	active = [e for e in employees if e.status == "Active"]
	active_ids = {e.name for e in active}

	def count_by(field, only_outsourced=False):
		out = {}
		for e in active:
			if only_outsourced and not e.get("custom_is_outsourced"):
				continue
			key = e.get(field) or _("Not Set")
			out[key] = out.get(key, 0) + 1
		return sorted(({"label": k, "value": v} for k, v in out.items()), key=lambda x: -x["value"])

	joiners = [
		e
		for e in employees
		if e.get("date_of_joining") and month_start <= getdate(e.date_of_joining) <= month_end
	]
	exits = [
		e
		for e in employees
		if e.get("relieving_date") and month_start <= getdate(e.relieving_date) <= month_end
	]

	summary = frappe._dict(
		total_active=len(active),
		inactive=sum(1 for e in employees if e.status == "Inactive"),
		left=sum(1 for e in employees if e.status == "Left"),
		joiners_this_month=len(joiners),
		exits_this_month=len(exits),
		present_today=0,
		absent_today=0,
		on_leave_today=0,
		wfh_today=0,
		half_day_today=0,
		checked_in_today=0,
		not_marked_today=0,
		pending_leaves=0,
		attendance_marked=False,
		outsourced=sum(1 for e in active if e.get("custom_is_outsourced")),
		own_staff=sum(1 for e in active if not e.get("custom_is_outsourced")),
		manpower_today=0,
		manpower_cost_month=0,
		manpower_own_month=0,
		manpower_outsourced_month=0,
	)

	# Manpower deployed on projects (Manpower Entries)
	manpower_by_project, manpower_by_agency = [], []
	if _doctype_exists("Manpower Entry"):
		mp_cond, mp_values = "", {"month_start": month_start, "month_end": month_end, "today": today}
		if filters.company:
			mp_cond = " AND me.company = %(company)s"
			mp_values["company"] = filters.company
		totals = frappe.db.sql(
			f"""
			SELECT SUM(CASE WHEN me.posting_date = %(today)s THEN d.no_of_workers ELSE 0 END) AS workers_today,
				SUM(CASE WHEN d.worker_type = 'Outsourced' THEN 0 ELSE d.amount END) AS own,
				SUM(CASE WHEN d.worker_type = 'Outsourced' THEN d.amount ELSE 0 END) AS outsourced
			FROM `tabManpower Entry Detail` d
			INNER JOIN `tabManpower Entry` me ON me.name = d.parent
			WHERE me.docstatus = 1 AND me.posting_date BETWEEN %(month_start)s AND %(month_end)s {mp_cond}
			""",
			mp_values,
			as_dict=True,
		)[0]
		summary.manpower_today = int(totals.workers_today or 0)
		summary.manpower_own_month = flt(totals.own)
		summary.manpower_outsourced_month = flt(totals.outsourced)
		summary.manpower_cost_month = summary.manpower_own_month + summary.manpower_outsourced_month
		manpower_by_project = [
			{"label": r.project, "value": flt(r.amount)}
			for r in frappe.db.sql(
				f"""
				SELECT me.project, SUM(d.amount) AS amount
				FROM `tabManpower Entry Detail` d
				INNER JOIN `tabManpower Entry` me ON me.name = d.parent
				WHERE me.docstatus = 1 AND me.posting_date BETWEEN %(month_start)s AND %(month_end)s {mp_cond}
				GROUP BY me.project ORDER BY amount DESC LIMIT 10
				""",
				mp_values,
				as_dict=True,
			)
		]
		manpower_by_agency = [
			{"label": r.supplier, "value": flt(r.amount), "workers": int(r.workers or 0)}
			for r in frappe.db.sql(
				f"""
				SELECT d.supplier, SUM(d.amount) AS amount, SUM(d.no_of_workers) AS workers
				FROM `tabManpower Entry Detail` d
				INNER JOIN `tabManpower Entry` me ON me.name = d.parent
				WHERE me.docstatus = 1 AND d.worker_type = 'Outsourced'
					AND me.posting_date BETWEEN %(month_start)s AND %(month_end)s {mp_cond}
				GROUP BY d.supplier ORDER BY amount DESC LIMIT 10
				""",
				mp_values,
				as_dict=True,
			)
		]

	# Attendance today + trend for the last 7 days
	trend = []
	if _doctype_exists("Attendance") and active_ids:
		start = add_days(today, -6)
		att = frappe.get_all(
			"Attendance",
			filters={
				"docstatus": 1,
				"attendance_date": ["between", [start, today]],
				"employee": ["in", list(active_ids)],
			},
			fields=["employee", "attendance_date", "status"],
			limit_page_length=0,
		)
		by_day = {}
		for a in att:
			d = str(getdate(a.attendance_date))
			by_day.setdefault(d, {}).setdefault(a.status, 0)
			by_day[d][a.status] += 1
		for i in range(7):
			d = str(add_days(start, i))
			s = by_day.get(d, {})
			trend.append(
				{
					"date": d,
					"present": s.get("Present", 0) + s.get("Work From Home", 0),
					"half_day": s.get("Half Day", 0),
					"absent": s.get("Absent", 0),
					"on_leave": s.get("On Leave", 0),
				}
			)
		todays = by_day.get(str(today), {})
		summary.present_today = todays.get("Present", 0)
		summary.wfh_today = todays.get("Work From Home", 0)
		summary.half_day_today = todays.get("Half Day", 0)
		summary.absent_today = todays.get("Absent", 0)
		summary.on_leave_today = todays.get("On Leave", 0)
		summary.attendance_marked = bool(todays)

	if _doctype_exists("Employee Checkin") and active_ids:
		summary.checked_in_today = len(
			set(
				frappe.get_all(
					"Employee Checkin",
					filters={
						"time": ["between", [f"{today} 00:00:00", f"{today} 23:59:59"]],
						"employee": ["in", list(active_ids)],
					},
					pluck="employee",
					limit_page_length=0,
				)
			)
		)

	leaves_today, pending_leaves = [], []
	if _doctype_exists("Leave Application") and active_ids:
		leaves_today = frappe.get_all(
			"Leave Application",
			filters={
				"docstatus": 1,
				"status": "Approved",
				"from_date": ["<=", today],
				"to_date": [">=", today],
				"employee": ["in", list(active_ids)],
			},
			fields=["name", "employee", "employee_name", "leave_type", "from_date", "to_date"],
			limit_page_length=0,
		)
		pending_leaves = frappe.get_all(
			"Leave Application",
			filters={"docstatus": 0, "status": "Open", "employee": ["in", list(active_ids)]},
			fields=[
				"name",
				"employee",
				"employee_name",
				"leave_type",
				"from_date",
				"to_date",
				"total_leave_days",
			],
			order_by="from_date asc",
			limit_page_length=0,
		)
		summary.pending_leaves = len(pending_leaves)
		if not summary.attendance_marked:
			summary.on_leave_today = len({lv.employee for lv in leaves_today})

	marked = (
		summary.present_today
		+ summary.wfh_today
		+ summary.half_day_today
		+ summary.absent_today
		+ summary.on_leave_today
	)
	summary.not_marked_today = max(summary.total_active - marked, 0) if summary.attendance_marked else 0

	# Birthdays, work anniversaries, passport expiry
	horizon = add_days(today, 30)
	birthdays, anniversaries, expiring = [], [], []
	for e in active:
		if e.get("date_of_birth"):
			nxt = _next_occurrence(getdate(e.date_of_birth), today)
			if nxt and nxt <= horizon:
				birthdays.append(
					{
						"employee": e.name,
						"employee_name": e.employee_name,
						"date": str(nxt),
						"department": e.get("department"),
						"days": (nxt - today).days,
					}
				)
		if e.get("date_of_joining"):
			doj = getdate(e.date_of_joining)
			nxt = _next_occurrence(doj, today)
			if nxt and nxt <= horizon and nxt.year > doj.year:
				anniversaries.append(
					{
						"employee": e.name,
						"employee_name": e.employee_name,
						"date": str(nxt),
						"years": nxt.year - doj.year,
						"days": (nxt - today).days,
					}
				)
		if has_passport and e.get("valid_upto"):
			exp = getdate(e.valid_upto)
			if exp <= add_days(today, 60):
				expiring.append(
					{
						"employee": e.name,
						"employee_name": e.employee_name,
						"document": _("Passport"),
						"number": e.get("passport_number"),
						"date": str(exp),
						"days": (exp - today).days,
					}
				)
	birthdays.sort(key=lambda x: x["days"])
	anniversaries.sort(key=lambda x: x["days"])
	expiring.sort(key=lambda x: x["days"])

	return {
		"summary": summary,
		"by_department": count_by("department"),
		"by_designation": count_by("designation")[:12],
		"by_gender": count_by("gender"),
		"by_employment_type": count_by("employment_type"),
		"by_agency": count_by("custom_manpower_supplier", only_outsourced=True),
		"manpower_by_project": manpower_by_project,
		"manpower_cost_by_agency": manpower_by_agency,
		"currency": frappe.get_cached_value("Company", filters.company, "default_currency")
		if filters.company
		else frappe.defaults.get_global_default("currency"),
		"attendance_trend": trend,
		"leaves_today": leaves_today,
		"pending_leaves": pending_leaves[:20],
		"birthdays": birthdays,
		"anniversaries": anniversaries,
		"expiring_documents": expiring,
		"new_joiners": [
			{
				"employee": e.name,
				"employee_name": e.employee_name,
				"department": e.get("department"),
				"designation": e.get("designation"),
				"date_of_joining": e.date_of_joining,
			}
			for e in sorted(joiners, key=lambda x: getdate(x.date_of_joining), reverse=True)
		],
		"exits": [
			{
				"employee": e.name,
				"employee_name": e.employee_name,
				"department": e.get("department"),
				"relieving_date": e.relieving_date,
			}
			for e in exits
		],
	}


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


def _company(filters):
	return (
		filters.get("company")
		or frappe.defaults.get_user_default("Company")
		or frappe.defaults.get_global_default("company")
		or frappe.db.get_value("Company", {}, "name")
	)


def _currency(company):
	return (
		frappe.get_cached_value("Company", company, "default_currency")
		if company
		else frappe.defaults.get_global_default("currency")
	)


# ---------------------------------------------------------------------------
# Stock Overview
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_stock_overview(filters=None):
	filters = _parse(filters)
	frappe.has_permission("Stock Ledger Entry", "read", throw=True)
	today = getdate(nowdate())
	month_start = get_first_day(today)
	company = filters.get("company")
	v = {
		"company": company,
		"today": today,
		"month_start": month_start,
		"d14": add_days(today, -13),
		"d90": add_days(today, -90),
		"warehouse": filters.get("warehouse"),
	}
	wh = " AND w.company = %(company)s" if company else ""
	if filters.get("warehouse"):
		wh += " AND b.warehouse = %(warehouse)s"
	sle_c = (" AND sle.company = %(company)s" if company else "") + (
		" AND sle.warehouse = %(warehouse)s" if filters.get("warehouse") else ""
	)

	totals = frappe.db.sql(
		f"""
		SELECT SUM(b.stock_value) AS value,
			COUNT(DISTINCT CASE WHEN b.actual_qty > 0 THEN b.item_code END) AS item_count,
			COUNT(DISTINCT CASE WHEN b.actual_qty > 0 THEN b.warehouse END) AS warehouses,
			SUM(b.actual_qty < 0) AS negative
		FROM `tabBin` b INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
		WHERE 1 = 1 {wh}
		""",
		v,
		as_dict=True,
	)[0]

	by_warehouse = frappe.db.sql(
		f"""
		SELECT b.warehouse AS label, SUM(b.stock_value) AS value
		FROM `tabBin` b INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
		WHERE b.stock_value != 0 {wh} GROUP BY b.warehouse ORDER BY value DESC LIMIT 8
		""",
		v,
		as_dict=True,
	)

	by_group = frappe.db.sql(
		f"""
		SELECT i.item_group AS label, SUM(b.stock_value) AS value
		FROM `tabBin` b INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
		INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE b.stock_value > 0 {wh} GROUP BY i.item_group ORDER BY value DESC
		""",
		v,
		as_dict=True,
	)
	if len(by_group) > 6:
		others = sum(flt(g.value) for g in by_group[5:])
		by_group = [*by_group[:5], frappe._dict(label=_("Others"), value=others)]

	top_items = frappe.db.sql(
		f"""
		SELECT b.item_code, i.item_name, i.stock_uom, SUM(b.actual_qty) AS qty, SUM(b.stock_value) AS value,
			COUNT(DISTINCT b.warehouse) AS warehouses
		FROM `tabBin` b INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
		INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE b.actual_qty > 0 {wh} GROUP BY b.item_code ORDER BY value DESC LIMIT 15
		""",
		v,
		as_dict=True,
	)

	reorder = frappe.db.sql(
		f"""
		SELECT ir.parent AS item_code, i.item_name, b.warehouse, b.actual_qty, b.projected_qty,
			ir.warehouse_reorder_level AS reorder_level, ir.warehouse_reorder_qty AS reorder_qty
		FROM `tabItem Reorder` ir
		INNER JOIN `tabBin` b ON b.item_code = ir.parent AND b.warehouse = ir.warehouse
		INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
		INNER JOIN `tabItem` i ON i.name = ir.parent
		WHERE ir.parenttype = 'Item' AND i.disabled = 0 AND b.projected_qty < ir.warehouse_reorder_level {wh}
		ORDER BY (ir.warehouse_reorder_level - b.projected_qty) DESC LIMIT 50
		""",
		v,
		as_dict=True,
	)

	slow = frappe.db.sql(
		f"""
		SELECT b.item_code, i.item_name, SUM(b.actual_qty) AS qty, SUM(b.stock_value) AS value
		FROM `tabBin` b INNER JOIN `tabWarehouse` w ON w.name = b.warehouse
		INNER JOIN `tabItem` i ON i.name = b.item_code
		WHERE b.actual_qty > 0 {wh}
			AND NOT EXISTS (
				SELECT 1 FROM `tabStock Ledger Entry` s
				WHERE s.item_code = b.item_code AND s.warehouse = b.warehouse
					AND s.posting_date >= %(d90)s AND s.is_cancelled = 0)
		GROUP BY b.item_code ORDER BY value DESC LIMIT 15
		""",
		v,
		as_dict=True,
	)

	movement = {
		str(r.day): r
		for r in frappe.db.sql(
			f"""
		SELECT sle.posting_date AS day,
			SUM(CASE WHEN sle.actual_qty > 0 THEN sle.stock_value_difference ELSE 0 END) AS stock_in,
			SUM(CASE WHEN sle.actual_qty < 0 THEN -sle.stock_value_difference ELSE 0 END) AS stock_out
		FROM `tabStock Ledger Entry` sle
		WHERE sle.is_cancelled = 0 AND sle.posting_date BETWEEN %(d14)s AND %(today)s {sle_c}
		GROUP BY sle.posting_date
		""",
			v,
			as_dict=True,
		)
	}
	trend = []
	for i in range(14):
		day = str(add_days(v["d14"], i))
		r = movement.get(day) or {}
		trend.append({"date": day, "in": flt(r.get("stock_in")), "out": flt(r.get("stock_out"))})

	month = frappe.db.sql(
		f"""
		SELECT SUM(CASE WHEN sle.actual_qty > 0 THEN sle.stock_value_difference ELSE 0 END) AS stock_in,
			SUM(CASE WHEN sle.actual_qty < 0 THEN -sle.stock_value_difference ELSE 0 END) AS stock_out
		FROM `tabStock Ledger Entry` sle
		WHERE sle.is_cancelled = 0 AND sle.posting_date BETWEEN %(month_start)s AND %(today)s {sle_c}
		""",
		v,
		as_dict=True,
	)[0]

	co = " AND po.company = %(company)s" if company else ""
	receipts = frappe.db.sql(
		f"""
		SELECT po.name, po.supplier, poi.item_code, poi.item_name, poi.schedule_date,
			(poi.qty - IFNULL(poi.received_qty, 0)) AS pending_qty, poi.uom,
			(poi.qty - IFNULL(poi.received_qty, 0)) * poi.base_rate AS value
		FROM `tabPurchase Order Item` poi INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
		INNER JOIN `tabItem` i ON i.name = poi.item_code
		WHERE po.docstatus = 1 AND po.status NOT IN ('Closed', 'Completed', 'On Hold')
			AND IFNULL(poi.delivered_by_supplier, 0) = 0 AND i.is_stock_item = 1
			AND poi.received_qty < poi.qty {co}
		ORDER BY poi.schedule_date ASC
		""",
		v,
		as_dict=True,
	)

	mr_c = " AND mr.company = %(company)s" if company else ""
	pending_mr = frappe.db.sql(
		f"""
		SELECT COUNT(*) FROM `tabMaterial Request` mr
		WHERE mr.docstatus = 1 AND mr.status IN ('Pending', 'Partially Ordered') {mr_c}
		""",
		v,
	)[0][0]

	se_c = " AND se.company = %(company)s" if company else ""
	by_project = frappe.db.sql(
		f"""
		SELECT se.project AS label, SUM(sed.amount) AS value
		FROM `tabStock Entry Detail` sed INNER JOIN `tabStock Entry` se ON se.name = sed.parent
		WHERE se.docstatus = 1 AND IFNULL(se.project, '') != '' AND IFNULL(sed.s_warehouse, '') != ''
			AND se.posting_date BETWEEN %(month_start)s AND %(today)s {se_c}
		GROUP BY se.project ORDER BY value DESC LIMIT 8
		""",
		v,
		as_dict=True,
	)
	recent = frappe.db.sql(
		f"""
		SELECT se.name, se.stock_entry_type, se.purpose, se.posting_date, se.project, se.total_outgoing_value,
			se.total_incoming_value, se.value_difference
		FROM `tabStock Entry` se WHERE se.docstatus = 1 {se_c}
		ORDER BY se.posting_date DESC, se.creation DESC LIMIT 12
		""",
		v,
		as_dict=True,
	)

	overdue_receipts = [r for r in receipts if r.schedule_date and getdate(r.schedule_date) < today]
	summary = frappe._dict(
		stock_value=flt(totals.value),
		items=int(totals.item_count or 0),
		warehouses=int(totals.warehouses or 0),
		negative=int(totals.negative or 0),
		below_reorder=len(reorder),
		pending_receipt_value=sum(flt(r.value) for r in receipts),
		pending_receipt_pos=len({r.name for r in receipts}),
		overdue_receipts=len({r.name for r in overdue_receipts}),
		pending_mr=int(pending_mr or 0),
		stock_in_month=flt(month.stock_in),
		stock_out_month=flt(month.stock_out),
		issued_to_projects=sum(flt(p.value) for p in by_project),
		slow_value=sum(flt(s.value) for s in slow),
	)
	return {
		"summary": summary,
		"by_warehouse": by_warehouse,
		"by_group": by_group,
		"top_items": top_items,
		"reorder": reorder[:20],
		"slow": slow,
		"trend": trend,
		"receipts": receipts[:20],
		"by_project": by_project,
		"recent": recent,
		"currency": _currency(company or _company(filters)),
	}


@frappe.whitelist()
def get_warehouses(company=None):
	filters = {"is_group": 0, "disabled": 0}
	if company:
		filters["company"] = company
	return frappe.get_list("Warehouse", filters=filters, pluck="name", order_by="name", limit_page_length=500)


# ---------------------------------------------------------------------------
# Accounts Overview
# ---------------------------------------------------------------------------

AGEING = (
	(None, 0, "Not due"),
	(1, 30, "1-30 days"),
	(31, 60, "31-60 days"),
	(61, 90, "61-90 days"),
	(91, None, "90+ days"),
)


def _ageing(rows, today):
	buckets = {label: 0.0 for _x, _y, label in AGEING}
	for r in rows:
		days = (today - getdate(r.due_date or r.posting_date)).days
		for lo, hi, label in AGEING:
			if (lo is None or days >= lo) and (hi is None or days <= hi):
				buckets[label] += flt(r.outstanding)
				break
	return [{"label": _(k), "value": v} for k, v in buckets.items()]


@frappe.whitelist()
def get_accounts_overview(filters=None):
	filters = _parse(filters)
	frappe.has_permission("GL Entry", "read", throw=True)
	company = _company(filters)
	today = getdate(nowdate())
	month_start = get_first_day(today)
	prev_start = get_first_day(add_days(month_start, -1))
	six_start = get_first_day(add_days(month_start, -150))
	try:
		from erpnext.accounts.utils import get_fiscal_year

		fy_start = get_fiscal_year(today, company=company)[1]
	except Exception:
		fy_start = today.replace(month=1, day=1)
	v = {
		"company": company,
		"today": today,
		"month_start": month_start,
		"prev_start": prev_start,
		"six_start": six_start,
		"fy_start": fy_start,
	}

	def open_invoices(doctype, party):
		return frappe.db.sql(
			f"""
			SELECT name, {party} AS party, posting_date, due_date, grand_total, outstanding_amount AS outstanding
			FROM `tab{doctype}`
			WHERE docstatus = 1 AND company = %(company)s AND outstanding_amount > 0
			ORDER BY due_date ASC
			""",
			v,
			as_dict=True,
		)

	receivables = open_invoices("Sales Invoice", "customer")
	payables = open_invoices("Purchase Invoice", "supplier")

	def party_totals(rows):
		out = {}
		for r in rows:
			out[r.party] = out.get(r.party, 0) + flt(r.outstanding)
		return [{"label": k, "value": val} for k, val in sorted(out.items(), key=lambda x: -x[1])[:8]]

	def overdue(rows):
		return [r for r in rows if r.due_date and getdate(r.due_date) < today]

	cash = frappe.db.sql(
		"""
		SELECT a.name AS account, a.account_name AS label, a.account_type, SUM(g.debit - g.credit) AS value
		FROM `tabGL Entry` g INNER JOIN `tabAccount` a ON a.name = g.account
		WHERE g.company = %(company)s AND g.is_cancelled = 0 AND a.account_type IN ('Bank', 'Cash')
		GROUP BY a.name ORDER BY value DESC
		""",
		v,
		as_dict=True,
	)

	pl = frappe.db.sql(
		"""
		SELECT DATE_FORMAT(g.posting_date, '%%Y-%%m') AS month, a.root_type,
			SUM(CASE WHEN a.root_type = 'Income' THEN g.credit - g.debit ELSE g.debit - g.credit END) AS amount
		FROM `tabGL Entry` g INNER JOIN `tabAccount` a ON a.name = g.account
		WHERE g.company = %(company)s AND g.is_cancelled = 0 AND a.root_type IN ('Income', 'Expense')
			AND g.voucher_type != 'Period Closing Voucher'
			AND g.posting_date BETWEEN %(six_start)s AND %(today)s
		GROUP BY month, a.root_type
		""",
		v,
		as_dict=True,
	)
	months = []
	cursor = six_start
	for _i in range(6):
		months.append(cursor.strftime("%Y-%m"))
		cursor = get_first_day(add_days(get_last_day(cursor), 1))
	by_month = {m: {"income": 0.0, "expense": 0.0} for m in months}
	for r in pl:
		if r.month in by_month:
			by_month[r.month]["income" if r.root_type == "Income" else "expense"] += flt(r.amount)
	trend = [{"month": m, **by_month[m]} for m in months]
	this_m = by_month.get(today.strftime("%Y-%m"), {"income": 0, "expense": 0})
	prev_m = by_month.get(prev_start.strftime("%Y-%m"), {"income": 0, "expense": 0})

	ytd = frappe.db.sql(
		"""
		SELECT SUM(CASE WHEN a.root_type = 'Income' THEN g.credit - g.debit ELSE 0 END) AS income,
			SUM(CASE WHEN a.root_type = 'Expense' THEN g.debit - g.credit ELSE 0 END) AS expense
		FROM `tabGL Entry` g INNER JOIN `tabAccount` a ON a.name = g.account
		WHERE g.company = %(company)s AND g.is_cancelled = 0 AND a.root_type IN ('Income', 'Expense')
			AND g.voucher_type != 'Period Closing Voucher' AND g.posting_date BETWEEN %(fy_start)s AND %(today)s
		""",
		v,
		as_dict=True,
	)[0]

	expense_split = frappe.db.sql(
		"""
		SELECT COALESCE(p.account_name, a.account_name) AS label, SUM(g.debit - g.credit) AS value
		FROM `tabGL Entry` g INNER JOIN `tabAccount` a ON a.name = g.account
		LEFT JOIN `tabAccount` p ON p.name = a.parent_account
		WHERE g.company = %(company)s AND g.is_cancelled = 0 AND a.root_type = 'Expense'
			AND g.voucher_type != 'Period Closing Voucher' AND g.posting_date BETWEEN %(month_start)s AND %(today)s
		GROUP BY label HAVING value > 0 ORDER BY value DESC
		""",
		v,
		as_dict=True,
	)
	if len(expense_split) > 6:
		expense_split = [
			*expense_split[:5],
			frappe._dict(label=_("Others"), value=sum(flt(e.value) for e in expense_split[5:])),
		]

	payments = frappe.db.sql(
		"""
		SELECT name, payment_type, party_type, party, posting_date, mode_of_payment,
			CASE WHEN payment_type = 'Receive' THEN base_received_amount ELSE base_paid_amount END AS amount
		FROM `tabPayment Entry`
		WHERE docstatus = 1 AND company = %(company)s
		ORDER BY posting_date DESC, creation DESC LIMIT 12
		""",
		v,
		as_dict=True,
	)
	flows = frappe.db.sql(
		"""
		SELECT SUM(CASE WHEN payment_type = 'Receive' THEN base_received_amount ELSE 0 END) AS received,
			SUM(CASE WHEN payment_type = 'Pay' THEN base_paid_amount ELSE 0 END) AS paid
		FROM `tabPayment Entry`
		WHERE docstatus = 1 AND company = %(company)s AND posting_date BETWEEN %(month_start)s AND %(today)s
		""",
		v,
		as_dict=True,
	)[0]

	rec_overdue, pay_overdue = overdue(receivables), overdue(payables)
	summary = frappe._dict(
		cash=sum(flt(c.value) for c in cash),
		receivable=sum(flt(r.outstanding) for r in receivables),
		receivable_overdue=sum(flt(r.outstanding) for r in rec_overdue),
		receivable_overdue_count=len(rec_overdue),
		payable=sum(flt(r.outstanding) for r in payables),
		payable_overdue=sum(flt(r.outstanding) for r in pay_overdue),
		payable_overdue_count=len(pay_overdue),
		income_month=flt(this_m["income"]),
		expense_month=flt(this_m["expense"]),
		income_prev=flt(prev_m["income"]),
		expense_prev=flt(prev_m["expense"]),
		income_ytd=flt(ytd.income),
		expense_ytd=flt(ytd.expense),
		profit_ytd=flt(ytd.income) - flt(ytd.expense),
		received_month=flt(flows.received),
		paid_month=flt(flows.paid),
		fy_start=str(fy_start),
	)
	return {
		"company": company,
		"summary": summary,
		"trend": trend,
		"cash": cash,
		"receivable_ageing": _ageing(receivables, today),
		"payable_ageing": _ageing(payables, today),
		"top_customers": party_totals(receivables),
		"top_suppliers": party_totals(payables),
		"overdue_sales": rec_overdue[:15],
		"overdue_purchases": pay_overdue[:15],
		"expense_split": expense_split,
		"payments": payments,
		"currency": _currency(company),
	}

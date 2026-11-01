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
	return {
		"companies": frappe.get_list("Company", pluck="name", order_by="name"),
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

	# Tasks
	task_stats = {}
	if names:
		for t in frappe.get_all(
			"Task",
			filters={"project": ["in", names]},
			fields=["project", "status", "exp_end_date"],
			limit_page_length=0,
		):
			s = task_stats.setdefault(t.project, {"total": 0, "open": 0, "overdue": 0, "completed": 0})
			s["total"] += 1
			if t.status == "Completed":
				s["completed"] += 1
			elif t.status != "Cancelled":
				s["open"] += 1
				if t.exp_end_date and getdate(t.exp_end_date) < today:
					s["overdue"] += 1

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
	]
	fields = [f for f in fields if f in ("name",) or meta.has_field(f)]
	has_passport = meta.has_field("valid_upto")
	if has_passport:
		fields += ["passport_number", "valid_upto"]

	employees = frappe.get_list("Employee", filters=emp_filters, fields=fields, limit_page_length=0)
	active = [e for e in employees if e.status == "Active"]
	active_ids = {e.name for e in active}

	def count_by(field):
		out = {}
		for e in active:
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
	)

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

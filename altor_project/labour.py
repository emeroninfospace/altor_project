# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Labour cost from Timesheets (normal hours, OT 1 and OT 2), and one labour cost source for
reports, dashboards and the Project Budget (Manpower Entries + Timesheets).

Hours on a Timesheet row are split into:

* Normal - up to the normal hours per day (Altor Settings: own staff 8, outsourced 10)
* OT 1   - hours above that on a working day (x OT 1 Multiplier, 1.25)
* OT 2   - all hours on a holiday / weekly off of the employee's Holiday List (x OT 2 Multiplier, 1.5)

Unless "Split Overtime Automatically" is unticked on the Timesheet, then OT 1 / OT 2 are entered by hand.

Cost of the hours (same as the client's calculation sheet):

* Own staff (Employee > Manpower Costing salary fields):
    normal hour = (Basic + Allowance + HRA + Transportation) / days in the month / hours per day
    OT hour     = Basic / days in the month / hours per day
    cost        = normal hours x normal hour + (OT 1 x 1.25 + OT 2 x 1.5) x OT hour
  Without salary fields: the Hourly Cost Rate / CTC rate of altor_project.manpower.
* Outsourced (Hourly Cost Rate on the Employee, else the agency rate in Altor Settings):
    cost = hourly rate x (normal hours + OT 1 x 1.25 + OT 2 x 1.5)
"""

import calendar

import frappe
from frappe import _
from frappe.utils import cint, flt, get_link_to_form, getdate

from altor_project.manpower import OUTSOURCED, OWN, get_employees, get_settings, resolve_rates

SALARY_FIELDS = ("custom_basic_salary", "custom_allowance", "custom_hra", "custom_transport_allowance")


# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------


def hour_rates(employee, on_date):
	"""(normal, OT 1, OT 2) cost per hour of an employee (dict from get_employees) on a date."""
	s = get_settings()
	if not employee:
		return 0.0, 0.0, 0.0
	outsourced = cint(employee.get("custom_is_outsourced"))
	if not outsourced and flt(employee.get("custom_basic_salary")):
		days = calendar.monthrange(getdate(on_date).year, getdate(on_date).month)[1]
		gross = sum(flt(employee.get(f)) for f in SALARY_FIELDS)
		normal = gross / days / s.hours
		ot_base = flt(employee.get("custom_basic_salary")) / days / s.hours
		return normal, ot_base * s.ot_multiplier, ot_base * s.ot2_multiplier

	worker_type = OUTSOURCED if outsourced else OWN
	supplier = employee.get("custom_manpower_supplier") if outsourced else None
	hourly, _ot = resolve_rates(worker_type, supplier, employee.get("designation"), employee)
	ot1 = flt(employee.get("custom_ot_hourly_rate")) or hourly * s.ot_multiplier
	return hourly, ot1, hourly * s.ot2_multiplier


def holiday_dates(employee, start, end):
	"""Holidays / weekly offs of the employee's Holiday List between two dates."""
	try:
		from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

		holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	except Exception:
		holiday_list = None
	if not holiday_list:
		return set()
	return {
		getdate(d)
		for d in frappe.get_all(
			"Holiday",
			filters={"parent": holiday_list, "holiday_date": ["between", [start, end]]},
			pluck="holiday_date",
		)
	}


# ---------------------------------------------------------------------------
# Timesheet doc events
# ---------------------------------------------------------------------------


def _has_fields(doc):
	return doc.meta.has_field("custom_worker_type") and frappe.get_meta("Timesheet Detail").has_field(
		"custom_labour_cost"
	)


def split_hours(rows, auto, hours_per_day, holidays):
	"""Fill custom_normal_hours / custom_ot1_hours / custom_ot2_hours on the rows (in place)."""
	used = {}
	for row in sorted(rows, key=lambda r: (str(r.from_time or ""), r.idx or 0)):
		hours = flt(row.hours)
		day = getdate(row.from_time) if row.from_time else None
		if auto:
			if day in holidays:
				row.custom_ot1_hours, row.custom_ot2_hours = 0, hours
			else:
				room = max(hours_per_day - used.get(day, 0), 0)
				row.custom_ot1_hours, row.custom_ot2_hours = max(hours - room, 0), 0
		ot = flt(row.custom_ot1_hours) + flt(row.custom_ot2_hours)
		if flt(row.custom_ot1_hours) < 0 or flt(row.custom_ot2_hours) < 0 or ot > hours + 1e-6:
			frappe.throw(
				_("Row #{0}: OT 1 + OT 2 hours ({1}) cannot be more than the hours worked ({2}).").format(
					row.idx, ot, hours
				)
			)
		row.custom_normal_hours = flt(hours - ot, 4)
		used[day] = used.get(day, 0) + row.custom_normal_hours


def calculate_timesheet(doc, method=None):
	"""doc_event (validate): split hours, cost them and use the cost as the Timesheet costing."""
	if not doc.get("employee") or not _has_fields(doc):
		return
	s = get_settings()
	employee = get_employees([doc.employee]).get(doc.employee)
	if not employee:
		return
	outsourced = cint(employee.get("custom_is_outsourced"))
	doc.custom_worker_type = OUTSOURCED if outsourced else OWN
	doc.custom_manpower_supplier = employee.get("custom_manpower_supplier") if outsourced else None
	item_group = (s.outsourced_item_group if outsourced else None) or s.item_group

	rows = [r for r in doc.get("time_logs") or []]
	days = [getdate(r.from_time) for r in rows if r.from_time]
	holidays = holiday_dates(doc.employee, min(days), max(days)) if days else set()
	normal_per_day = s.outsourced_hours if outsourced else s.hours
	split_hours(rows, cint(doc.get("custom_auto_overtime")), normal_per_day, holidays)

	totals = frappe._dict(normal=0, ot1=0, ot2=0, cost=0, ot_cost=0)
	no_rate = []
	for row in rows:
		normal_rate, ot1_rate, ot2_rate = hour_rates(employee, row.from_time or doc.get("start_date"))
		ot_cost = flt(row.custom_ot1_hours) * ot1_rate + flt(row.custom_ot2_hours) * ot2_rate
		# rows keep extra decimals so monthly totals match the salary sheet (rounded once)
		row.custom_ot_cost = flt(ot_cost, 6)
		row.custom_labour_cost = flt(flt(row.custom_normal_hours) * normal_rate + ot_cost, 6)
		row.custom_item_group = item_group
		if flt(row.hours) and not normal_rate:
			no_rate.append(row)
		# ERPNext project costing (Project > Total Costing Amount) uses the same figure
		row.costing_rate = flt(row.custom_labour_cost / flt(row.hours), 6) if flt(row.hours) else 0
		row.costing_amount = row.custom_labour_cost
		totals.normal += flt(row.custom_normal_hours)
		totals.ot1 += flt(row.custom_ot1_hours)
		totals.ot2 += flt(row.custom_ot2_hours)
		totals.cost += row.custom_labour_cost
		totals.ot_cost += row.custom_ot_cost

	doc.custom_total_normal_hours = totals.normal
	doc.custom_total_ot1_hours = totals.ot1
	doc.custom_total_ot2_hours = totals.ot2
	doc.custom_total_ot_cost = flt(totals.ot_cost, 2)
	doc.custom_total_labour_cost = flt(totals.cost, 2)
	doc.total_costing_amount = flt(sum(flt(r.costing_amount) for r in rows), 2)
	if doc.meta.has_field("base_total_costing_amount"):
		doc.base_total_costing_amount = doc.total_costing_amount

	if no_rate:
		frappe.msgprint(
			_(
				"No cost rate for {0}. Fill Basic Salary (own staff) or Hourly Cost Rate (outsourced) on the Employee under Manpower Costing."
			).format(get_link_to_form("Employee", doc.employee)),
			title=_("Labour Cost Missing"),
			indicator="orange",
		)
	warn_manpower_entries(doc, days)


def warn_manpower_entries(doc, days):
	"""Hours booked on a Manpower Entry and a Timesheet would be costed twice."""
	if not days:
		return
	clash = frappe.db.sql(
		"""
		SELECT DISTINCT me.name, me.posting_date
		FROM `tabManpower Entry Detail` d
		INNER JOIN `tabManpower Entry` me ON me.name = d.parent
		WHERE me.docstatus = 1 AND d.employee = %s AND me.posting_date IN %s
		""",
		(doc.employee, tuple({str(d) for d in days})),
		as_dict=True,
	)
	if clash:
		frappe.msgprint(
			_(
				"{0} is also booked on Manpower Entries for the same days ({1}). The cost would be counted twice in the project budget; cancel one of them."
			).format(doc.employee_name or doc.employee, ", ".join(sorted({c.name for c in clash}))),
			title=_("Booked Twice"),
			indicator="orange",
		)


def on_timesheet_change(doc, method=None):
	"""doc_event (on_submit / on_cancel): refresh the budgets of the projects on the Timesheet."""
	from altor_project.budget import queue_budget_update

	for project in {r.project for r in doc.get("time_logs") or [] if r.get("project")}:
		queue_budget_update(project)


# ---------------------------------------------------------------------------
# One labour cost source: Manpower Entries + Timesheets
# ---------------------------------------------------------------------------


def timesheets_enabled():
	return frappe.db.has_column("Timesheet Detail", "custom_labour_cost") and frappe.db.has_column(
		"Timesheet", "custom_worker_type"
	)


def labour_sql():
	"""SELECT of submitted labour cost lines, to use as `FROM ({labour_sql()}) l`.

	Columns: source, voucher, project, posting_date, company, worker_type, supplier, employee,
	employee_name, designation, item_group, no_of_workers, hours, ot_hours, ot2_hours, amount.
	Timesheet lines are per employee, day, project and item group (no_of_workers = 1).
	"""
	parts = [
		"""
		SELECT 'Manpower Entry' AS source, me.name AS voucher, me.project, me.posting_date, me.company,
			IFNULL(NULLIF(d.worker_type, ''), 'Own Staff') AS worker_type, d.supplier, d.employee,
			d.employee_name, d.designation, COALESCE(NULLIF(d.item_group, ''), me.item_group) AS item_group,
			IFNULL(d.no_of_workers, 0) AS no_of_workers,
			IFNULL(d.no_of_workers, 0) * IFNULL(d.working_hours, 0) AS hours,
			IFNULL(d.no_of_workers, 0) * IFNULL(d.ot_hours, 0) AS ot_hours,
			0 AS ot2_hours, IFNULL(d.amount, 0) AS amount
		FROM `tabManpower Entry Detail` d
		INNER JOIN `tabManpower Entry` me ON me.name = d.parent
		WHERE me.docstatus = 1
		"""
	]
	if timesheets_enabled():
		parts.append(
			"""
			SELECT 'Timesheet' AS source, ts.name AS voucher, td.project, DATE(td.from_time) AS posting_date,
				ts.company, IFNULL(NULLIF(ts.custom_worker_type, ''), 'Own Staff') AS worker_type,
				ts.custom_manpower_supplier AS supplier, ts.employee, ts.employee_name, e.designation,
				td.custom_item_group AS item_group, 1 AS no_of_workers,
				SUM(IFNULL(td.custom_normal_hours, 0)) AS hours, SUM(IFNULL(td.custom_ot1_hours, 0)) AS ot_hours,
				SUM(IFNULL(td.custom_ot2_hours, 0)) AS ot2_hours, SUM(IFNULL(td.custom_labour_cost, 0)) AS amount
			FROM `tabTimesheet Detail` td
			INNER JOIN `tabTimesheet` ts ON ts.name = td.parent
			LEFT JOIN `tabEmployee` e ON e.name = ts.employee
			WHERE ts.docstatus = 1 AND IFNULL(td.project, '') != ''
			GROUP BY ts.name, td.project, DATE(td.from_time), td.custom_item_group, ts.company,
				ts.custom_worker_type, ts.custom_manpower_supplier, ts.employee, ts.employee_name, e.designation
			"""
		)
	return " UNION ALL ".join(parts)

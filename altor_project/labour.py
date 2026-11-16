# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Labour cost from Timesheets (normal hours, OT 1 and OT 2), used by the Project Budget,
the dashboards and the manpower reports.

Hours on a Timesheet row are split into:

* Normal - up to the normal hours per day (Altor Settings: own staff 8, outsourced 10)
* OT 1   - hours above that on a working day (x OT 1 Multiplier, 1.25)
* OT 2   - all hours on a holiday / weekly off of the employee's Holiday List (x OT 2 Multiplier, 1.5)

Unless "Split Overtime Automatically" is unticked on the Timesheet, then OT 1 / OT 2 are entered by hand.

Cost of the hours (the client's calculation sheet):

* Own staff (Employee > Manpower Costing salary fields):
    normal hour = (Basic + Allowance + HRA + Transportation) / days in the month / hours per day
    OT hour     = Basic / days in the month / hours per day
    cost        = normal hours x normal hour + (OT 1 x 1.25 + OT 2 x 1.5) x OT hour
  Without a Basic Salary the Hourly Cost Rate on the Employee is used like for outsourced staff.
* Outsourced (Hourly Cost Rate on the Employee):
    cost = hourly rate x (normal hours + OT 1 x 1.25 + OT 2 x 1.5)
"""

import calendar

import frappe
from frappe import _
from frappe.utils import cint, flt, get_link_to_form, getdate

OWN = "Own Staff"
OUTSOURCED = "Outsourced"
SALARY_FIELDS = ("custom_basic_salary", "custom_allowance", "custom_hra", "custom_transport_allowance")
EMPLOYEE_FIELDS = (
	"custom_is_outsourced",
	"custom_manpower_supplier",
	"custom_hourly_cost_rate",
	*SALARY_FIELDS,
)


def get_settings():
	s = frappe.get_cached_doc("Altor Settings")
	hours = flt(s.get("working_hours_per_day")) or 8
	return frappe._dict(
		item_group=s.get("default_manpower_item_group"),
		outsourced_item_group=s.get("outsourced_manpower_item_group") or s.get("default_manpower_item_group"),
		ot_multiplier=flt(s.get("ot_multiplier")) or 1.25,
		ot2_multiplier=flt(s.get("ot2_multiplier")) or 1.5,
		hours=hours,
		outsourced_hours=flt(s.get("outsourced_hours_per_day")) or hours,
	)


def get_employee(name):
	meta = frappe.get_meta("Employee")
	fields = ["name", "employee_name", "designation"] + [f for f in EMPLOYEE_FIELDS if meta.has_field(f)]
	return frappe.db.get_value("Employee", name, fields, as_dict=True)


# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------


def hour_rates(employee, on_date, s=None):
	"""(normal, OT 1, OT 2) cost per hour of an employee on a date."""
	s = s or get_settings()
	if not employee:
		return 0.0, 0.0, 0.0
	if not cint(employee.get("custom_is_outsourced")) and flt(employee.get("custom_basic_salary")):
		day = getdate(on_date)
		days = calendar.monthrange(day.year, day.month)[1]
		normal = sum(flt(employee.get(f)) for f in SALARY_FIELDS) / days / s.hours
		ot_base = flt(employee.custom_basic_salary) / days / s.hours
		return normal, ot_base * s.ot_multiplier, ot_base * s.ot2_multiplier
	hourly = flt(employee.get("custom_hourly_cost_rate"))
	return hourly, hourly * s.ot_multiplier, hourly * s.ot2_multiplier


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
	if not doc.get("employee") or not doc.meta.has_field("custom_worker_type"):
		return
	employee = get_employee(doc.employee)
	if not employee:
		return
	s = get_settings()
	outsourced = cint(employee.get("custom_is_outsourced"))
	doc.custom_worker_type = OUTSOURCED if outsourced else OWN
	doc.custom_manpower_supplier = employee.get("custom_manpower_supplier") if outsourced else None
	item_group = s.outsourced_item_group if outsourced else s.item_group

	rows = list(doc.get("time_logs") or [])
	days = [getdate(r.from_time) for r in rows if r.from_time]
	holidays = holiday_dates(doc.employee, min(days), max(days)) if days else set()
	split_hours(
		rows, cint(doc.get("custom_auto_overtime")), s.outsourced_hours if outsourced else s.hours, holidays
	)

	totals = frappe._dict(normal=0, ot1=0, ot2=0, cost=0, ot_cost=0)
	missing_rate = False
	for row in rows:
		normal_rate, ot1_rate, ot2_rate = hour_rates(employee, row.from_time or doc.get("start_date"), s)
		ot_cost = flt(row.custom_ot1_hours) * ot1_rate + flt(row.custom_ot2_hours) * ot2_rate
		# rows keep extra decimals so monthly totals match the salary sheet (rounded once)
		row.custom_ot_cost = flt(ot_cost, 6)
		row.custom_labour_cost = flt(flt(row.custom_normal_hours) * normal_rate + ot_cost, 6)
		row.custom_item_group = item_group
		missing_rate = missing_rate or bool(flt(row.hours) and not normal_rate)
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
	doc.total_costing_amount = doc.custom_total_labour_cost
	if doc.meta.has_field("base_total_costing_amount"):
		doc.base_total_costing_amount = doc.total_costing_amount

	if missing_rate:
		frappe.msgprint(
			_(
				"No cost rate for {0}. Fill Basic Salary (own staff) or Hourly Cost Rate (outsourced) on the Employee under Manpower Costing."
			).format(get_link_to_form("Employee", doc.employee)),
			title=_("Labour Cost Missing"),
			indicator="orange",
		)


def on_timesheet_change(doc, method=None):
	"""doc_event (on_submit / on_cancel): refresh the budgets of the projects on the Timesheet."""
	from altor_project.budget import queue_budget_update

	for project in {r.project for r in doc.get("time_logs") or [] if r.get("project")}:
		queue_budget_update(project)


# ---------------------------------------------------------------------------
# Labour cost lines for reports, dashboards and the budget
# ---------------------------------------------------------------------------

_COLUMNS = (
	"voucher, project, posting_date, company, worker_type, supplier, employee, employee_name, designation, "
	"item_group, no_of_workers, hours, ot_hours, ot2_hours, amount"
)


def labour_sql():
	"""SELECT of submitted Timesheet labour, to use as `FROM ({labour_sql()}) l`.

	One line per employee, day, project and item group, with the columns in _COLUMNS
	(hours = normal hours, ot_hours = OT 1, ot2_hours = OT 2, no_of_workers = 1).
	"""
	if not frappe.db.has_column("Timesheet Detail", "custom_labour_cost"):
		# before the Timesheet fields exist: no rows, same columns
		return (
			"SELECT "
			+ ", ".join(f"NULL AS {c.strip()}" for c in _COLUMNS.split(","))
			+ " FROM DUAL WHERE 1 = 0"
		)
	return """
		SELECT ts.name AS voucher, td.project, DATE(td.from_time) AS posting_date, ts.company,
			IFNULL(NULLIF(ts.custom_worker_type, ''), 'Own Staff') AS worker_type,
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

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
* Outsourced (Hourly Charge on the Employee, no salary fields):
    cost = hourly rate x (normal hours + OT 1 x 1.25 + OT 2 x 1.5)
"""

import calendar

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, get_link_to_form, getdate

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
	"""(normal, OT 1, OT 2) cost per hour of an employee on a date.

	Own staff: from the monthly salary fields. Outsourced: the agency's hourly charge.
	"""
	s = s or get_settings()
	if not employee:
		return 0.0, 0.0, 0.0
	if cint(employee.get("custom_is_outsourced")):
		hourly = flt(employee.get("custom_hourly_cost_rate"))
		return hourly, hourly * s.ot_multiplier, hourly * s.ot2_multiplier
	basic = flt(employee.get("custom_basic_salary"))
	if not basic:
		return 0.0, 0.0, 0.0
	day = getdate(on_date)
	days = calendar.monthrange(day.year, day.month)[1]
	normal = sum(flt(employee.get(f)) for f in SALARY_FIELDS) / days / s.hours
	ot_base = basic / days / s.hours
	return normal, ot_base * s.ot_multiplier, ot_base * s.ot2_multiplier


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


MIXED = "Mixed"
ROW_EMPLOYEE = "custom_employee"


def row_employee(doc, row):
	"""The employee of a Timesheet row: the row's own (crew Timesheet) or the Timesheet's."""
	return row.get(ROW_EMPLOYEE) or doc.get("employee")


def calculate_timesheet(doc, method=None):
	"""doc_event (validate): split hours, cost them and use the cost as the Timesheet costing.

	A Timesheet is for one employee (Employee at the top), or for a crew: the top left empty and an
	Employee on each row (several employees and projects on one Timesheet)."""
	if not doc.meta.has_field("custom_worker_type"):
		return
	rows = list(doc.get("time_logs") or [])
	row_meta = frappe.get_meta("Timesheet Detail")
	has_row_employee = row_meta.has_field(ROW_EMPLOYEE)
	has_row_type = row_meta.has_field("custom_worker_type")
	if doc.get("employee") and has_row_employee:
		for row in rows:
			row.set(ROW_EMPLOYEE, doc.employee)  # one-employee Timesheet: every row is theirs
	if not any(row_employee(doc, r) for r in rows):
		return  # nobody's labour (e.g. a user's own Timesheet without an employee)
	missing = [str(r.idx) for r in rows if not row_employee(doc, r)]
	if missing:
		frappe.throw(
			_("Select the Employee on rows {0} (or one Employee at the top).").format(", ".join(missing))
		)

	s = get_settings()
	auto = cint(doc.get("custom_auto_overtime"))
	by_employee = {}
	for row in rows:
		by_employee.setdefault(row_employee(doc, row), []).append(row)

	totals = frappe._dict(normal=0, ot1=0, ot2=0, cost=0, ot_cost=0)
	types, suppliers, no_rate = set(), set(), []
	for name, emp_rows in by_employee.items():
		employee = get_employee(name)
		if not employee:
			frappe.throw(_("Employee {0} not found.").format(name))
		outsourced = cint(employee.get("custom_is_outsourced"))
		worker_type = OUTSOURCED if outsourced else OWN
		supplier = employee.get("custom_manpower_supplier") if outsourced else None
		types.add(worker_type)
		if supplier:
			suppliers.add(supplier)
		days = [getdate(r.from_time) for r in emp_rows if r.from_time]
		holidays = holiday_dates(name, min(days), max(days)) if days else set()
		# normal hours per day are counted per employee, so each one's overtime is right on a crew sheet
		split_hours(emp_rows, auto, s.outsourced_hours if outsourced else s.hours, holidays)
		for row in emp_rows:
			normal_rate, ot1_rate, ot2_rate = hour_rates(employee, row.from_time or doc.get("start_date"), s)
			ot_cost = flt(row.custom_ot1_hours) * ot1_rate + flt(row.custom_ot2_hours) * ot2_rate
			# rows keep extra decimals so monthly totals match the salary sheet (rounded once)
			row.custom_ot_cost = flt(ot_cost, 6)
			row.custom_labour_cost = flt(flt(row.custom_normal_hours) * normal_rate + ot_cost, 6)
			row.custom_item_group = s.outsourced_item_group if outsourced else s.item_group
			if has_row_type:
				row.custom_worker_type = worker_type
				row.custom_manpower_supplier = supplier
			if flt(row.hours) and not normal_rate and name not in no_rate:
				no_rate.append(name)
			# ERPNext project costing (Project > Total Costing Amount) uses the same figure
			row.costing_rate = flt(row.custom_labour_cost / flt(row.hours), 6) if flt(row.hours) else 0
			row.costing_amount = row.custom_labour_cost
			totals.normal += flt(row.custom_normal_hours)
			totals.ot1 += flt(row.custom_ot1_hours)
			totals.ot2 += flt(row.custom_ot2_hours)
			totals.cost += row.custom_labour_cost
			totals.ot_cost += row.custom_ot_cost

	doc.custom_worker_type = types.pop() if len(types) == 1 else MIXED
	doc.custom_manpower_supplier = suppliers.pop() if len(suppliers) == 1 else None
	if not doc.get("employee") and doc.meta.has_field("title"):
		doc.title = (
			_("Crew: {0} employees").format(len(by_employee))
			if len(by_employee) > 1
			else (get_employee(next(iter(by_employee))) or {}).get("employee_name")
		)
	doc.custom_total_normal_hours = totals.normal
	doc.custom_total_ot1_hours = totals.ot1
	doc.custom_total_ot2_hours = totals.ot2
	doc.custom_total_ot_cost = flt(totals.ot_cost, 2)
	doc.custom_total_labour_cost = flt(totals.cost, 2)
	doc.total_costing_amount = doc.custom_total_labour_cost
	if doc.meta.has_field("base_total_costing_amount"):
		doc.base_total_costing_amount = doc.total_costing_amount

	if no_rate:
		frappe.msgprint(
			_(
				"No cost rate for {0}. Fill the salary (own staff) or the Hourly Charge (outsourced) on the Employee under Manpower Costing."
			).format(", ".join(get_link_to_form("Employee", n) for n in no_rate)),
			title=_("Labour Cost Missing"),
			indicator="orange",
		)


def validate_employee_overlap(doc, method=None):
	"""doc_event (Timesheet validate): an employee's rows may not overlap, on this Timesheet or another
	(ERPNext checks the Timesheet's Employee only; on a crew Timesheet each row has its own)."""
	if not frappe.get_meta("Timesheet Detail").has_field(ROW_EMPLOYEE):
		return
	if cint(frappe.db.get_single_value("Projects Settings", "ignore_employee_time_overlap")):
		return
	rows = [r for r in doc.get("time_logs") or [] if row_employee(doc, r) and r.from_time and r.to_time]
	for i, row in enumerate(rows):
		emp, start, end = row_employee(doc, row), get_datetime(row.from_time), get_datetime(row.to_time)
		for other in rows[i + 1 :]:
			if (
				row_employee(doc, other) == emp
				and start < get_datetime(other.to_time)
				and get_datetime(other.from_time) < end
			):
				frappe.throw(
					_("Rows {0} and {1}: the hours of {2} overlap.").format(row.idx, other.idx, emp),
					title=_("Overlapping Hours"),
				)
		clash = frappe.db.sql(
			f"""
			SELECT ts.name FROM `tabTimesheet Detail` td
			INNER JOIN `tabTimesheet` ts ON ts.name = td.parent
			WHERE ts.docstatus < 2 AND ts.name != %(name)s
				AND COALESCE(NULLIF(td.{ROW_EMPLOYEE}, ''), ts.employee) = %(emp)s
				AND td.from_time < %(end)s AND td.to_time > %(start)s
			LIMIT 1
			""",
			{"name": doc.name or "", "emp": emp, "start": start, "end": end},
		)
		if clash:
			frappe.throw(
				_("Row {0}: the hours of {1} overlap with Timesheet {2}.").format(
					row.idx, emp, get_link_to_form("Timesheet", clash[0][0])
				),
				title=_("Overlapping Hours"),
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
	if frappe.db.has_column("Timesheet Detail", ROW_EMPLOYEE):
		# crew Timesheets: each row has its own employee, worker type and agency
		emp = f"COALESCE(NULLIF(td.{ROW_EMPLOYEE}, ''), ts.employee)"
		wtype = "COALESCE(NULLIF(td.custom_worker_type, ''), NULLIF(ts.custom_worker_type, ''), 'Own Staff')"
		supplier = "COALESCE(NULLIF(td.custom_manpower_supplier, ''), ts.custom_manpower_supplier)"
	else:
		emp, supplier = "ts.employee", "ts.custom_manpower_supplier"
		wtype = "IFNULL(NULLIF(ts.custom_worker_type, ''), 'Own Staff')"
	# row values first, then grouped by plain columns (MariaDB's ONLY_FULL_GROUP_BY)
	return f"""
		SELECT voucher, project, posting_date, company, worker_type, supplier, employee, employee_name,
			designation, item_group, 1 AS no_of_workers, SUM(hours) AS hours, SUM(ot_hours) AS ot_hours,
			SUM(ot2_hours) AS ot2_hours, SUM(amount) AS amount
		FROM (
			SELECT ts.name AS voucher, td.project, DATE(td.from_time) AS posting_date, ts.company,
				{wtype} AS worker_type, {supplier} AS supplier, {emp} AS employee,
				IFNULL(e.employee_name, ts.employee_name) AS employee_name, e.designation,
				td.custom_item_group AS item_group,
				IFNULL(td.custom_normal_hours, 0) AS hours, IFNULL(td.custom_ot1_hours, 0) AS ot_hours,
				IFNULL(td.custom_ot2_hours, 0) AS ot2_hours, IFNULL(td.custom_labour_cost, 0) AS amount
			FROM `tabTimesheet Detail` td
			INNER JOIN `tabTimesheet` ts ON ts.name = td.parent
			LEFT JOIN `tabEmployee` e ON e.name = {emp}
			WHERE ts.docstatus = 1 AND IFNULL(td.project, '') != ''
		) labour_rows
		GROUP BY voucher, project, posting_date, company, worker_type, supplier, employee, employee_name,
			designation, item_group
	"""

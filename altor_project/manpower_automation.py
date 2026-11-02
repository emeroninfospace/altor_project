# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Create Manpower Entries automatically.

For a date, one Manpower Entry per project is built from:

* Named workers (own staff and outsourced Employees)
  - "Attendance": submitted Attendance (Present / Work From Home / Half Day).
    Hours = Working Hours on the attendance, or the standard day (half for Half Day).
  - "Employee Checkin": first IN to last OUT of the day.
  The project is the Project on the checkin, else the employee's Assigned Project.
  Hours above the standard day (Altor Settings > Working Hours per Day) become OT.

* Agency crews from each open project's Daily Manpower Crew table
  (active on that date, skipped on holidays if set).

Employees already booked in another Manpower Entry that day, and crews already
booked for the project that day, are skipped, so running it twice is safe.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_datetime, getdate, nowdate, time_diff_in_hours

from altor_project.manpower import OUTSOURCED, OWN, get_employees, get_settings, resolve_rates

WORKED_STATUSES = ("Present", "Work From Home", "Half Day")


def scheduled_create():
	"""Scheduler: book yesterday when automation is enabled."""
	if not cint(frappe.db.get_single_value("Altor Settings", "auto_create_manpower_entries")):
		return
	result = create_entries_for_date(add_days(nowdate(), -1))
	if result["errors"]:
		frappe.log_error(title="Manpower Entry automation", message=frappe.as_json(result, indent=1))


@frappe.whitelist()
def create_manpower_entries(date=None, source=None, submit=None):
	"""Button on the Manpower Entry list: create entries for one date now."""
	frappe.has_permission("Manpower Entry", "create", throw=True)
	date = getdate(date or add_days(nowdate(), -1))
	if date > getdate(nowdate()):
		frappe.throw(_("Manpower Entries cannot be created for a future date."))
	return create_entries_for_date(date, source=source, submit=submit)


def create_entries_for_date(date, source=None, submit=None):
	date = getdate(date)
	settings = frappe.get_cached_doc("Altor Settings")
	source = source or settings.get("manpower_entry_source") or "Attendance"
	submit = cint(settings.get("auto_submit_manpower_entries")) if submit is None else cint(submit)
	std_hours = get_settings().hours
	result = {"date": str(date), "created": [], "skipped": [], "errors": []}

	rows_by_project = {}
	worker_rows, skipped = _worker_rows(date, source, std_hours)
	result["skipped"] += skipped
	for project, row in worker_rows:
		rows_by_project.setdefault(project, []).append(row)

	crew_rows, skipped = _crew_rows(date, settings)
	result["skipped"] += skipped
	for project, row in crew_rows:
		rows_by_project.setdefault(project, []).append(row)

	for project, rows in rows_by_project.items():
		savepoint = "manpower_auto"
		frappe.db.savepoint(savepoint)
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Manpower Entry",
					"project": project,
					"posting_date": date,
					"item_group": get_settings().item_group,
					"auto_created": 1,
					"remarks": _("Created automatically from {0} and Daily Manpower Crew").format(_(source)),
					"details": rows,
				}
			)
			doc.flags.ignore_permissions = True
			doc.insert()
			if submit:
				doc.submit()
			result["created"].append(doc.name)
		except Exception as e:
			frappe.db.rollback(save_point=savepoint)
			result["errors"].append(f"{project}: {frappe.utils.strip_html(str(e))[:300]}")
		finally:
			frappe.clear_messages()
	frappe.db.commit()
	return result


# ---------------------------------------------------------------------------
# Named workers
# ---------------------------------------------------------------------------


def _already_booked(date):
	"""Employees already in a (draft or submitted) Manpower Entry on the date."""
	return set(
		frappe.db.sql_list(
			"""
			SELECT DISTINCT d.employee FROM `tabManpower Entry Detail` d
			INNER JOIN `tabManpower Entry` me ON me.name = d.parent
			WHERE me.docstatus < 2 AND me.posting_date = %s AND IFNULL(d.employee, '') != ''
			""",
			date,
		)
	)


def _worked_hours(date, source, std_hours):
	"""{employee: (hours, project_from_checkin or None)}"""
	worked = {}
	if source == "Employee Checkin":
		if not frappe.db.exists("DocType", "Employee Checkin"):
			return worked
		has_project = frappe.db.has_column("Employee Checkin", "custom_project")
		logs = frappe.get_all(
			"Employee Checkin",
			filters={"time": ["between", [f"{date} 00:00:00", f"{date} 23:59:59"]]},
			fields=["employee", "time", "log_type"] + (["custom_project"] if has_project else []),
			order_by="time asc",
		)
		by_emp = {}
		for log in logs:
			by_emp.setdefault(log.employee, []).append(log)
		for emp, emp_logs in by_emp.items():
			ins = [log for log in emp_logs if log.log_type != "OUT"] or emp_logs
			outs = [log for log in emp_logs if log.log_type == "OUT"]
			first_in = get_datetime(ins[0].time)
			last_out = get_datetime(outs[-1].time) if outs else None
			hours = time_diff_in_hours(last_out, first_in) if last_out and last_out > first_in else std_hours
			project = next((log.get("custom_project") for log in emp_logs if log.get("custom_project")), None)
			worked[emp] = (round(hours, 2), project)
	else:
		if not frappe.db.exists("DocType", "Attendance"):
			return worked
		for a in frappe.get_all(
			"Attendance",
			filters={"docstatus": 1, "attendance_date": date, "status": ["in", WORKED_STATUSES]},
			fields=["employee", "status", "working_hours"],
		):
			hours = flt(a.working_hours) or (std_hours / 2 if a.status == "Half Day" else std_hours)
			worked[a.employee] = (round(hours, 2), None)
	return worked


def _worker_rows(date, source, std_hours):
	worked = _worked_hours(date, source, std_hours)
	booked = _already_booked(date)
	todo = [e for e in worked if e not in booked]
	employees = get_employees(todo)
	assigned = {}
	if todo and frappe.db.has_column("Employee", "custom_current_project"):
		assigned = dict(
			frappe.get_all(
				"Employee",
				filters={"name": ["in", todo]},
				fields=["name", "custom_current_project"],
				as_list=True,
			)
		)
	open_projects = _open_projects()

	rows, skipped = [], []
	for emp in todo:
		info = employees.get(emp)
		if not info:
			continue
		hours, checkin_project = worked[emp]
		project = checkin_project or assigned.get(emp)
		if not project or hours <= 0:
			continue  # office staff etc. not deployed on a project
		if project not in open_projects:
			skipped.append(_("{0}: project {1} is not open").format(info.employee_name, project))
			continue
		worker_type = OUTSOURCED if info.get("custom_is_outsourced") else OWN
		supplier = info.get("custom_manpower_supplier") if worker_type == OUTSOURCED else None
		hourly, ot_rate = resolve_rates(worker_type, supplier, info.designation, info)
		if not hourly:
			skipped.append(_("{0}: no hourly rate").format(info.employee_name))
			continue
		normal = min(hours, std_hours)
		rows.append(
			(
				project,
				{
					"worker_type": worker_type,
					"employee": emp,
					"supplier": supplier,
					"designation": info.designation,
					"no_of_workers": 1,
					"working_hours": normal,
					"ot_hours": round(max(hours - std_hours, 0), 2),
					"hourly_rate": hourly,
					"ot_hourly_rate": ot_rate,
				},
			)
		)
	return rows, skipped


# ---------------------------------------------------------------------------
# Agency crews
# ---------------------------------------------------------------------------


def _open_projects():
	return set(frappe.get_all("Project", filters={"status": "Open"}, pluck="name"))


def _is_holiday(company, date, cache):
	key = (company, str(date))
	if key not in cache:
		holiday_list = (
			frappe.get_cached_value("Company", company, "default_holiday_list") if company else None
		)
		cache[key] = bool(
			holiday_list and frappe.db.exists("Holiday", {"parent": holiday_list, "holiday_date": date})
		)
	return cache[key]


def _crew_rows(date, settings):
	if not frappe.db.exists("DocType", "Project Manpower Crew"):
		return [], []
	crews = frappe.db.sql(
		"""
		SELECT c.parent AS project, p.company, c.supplier, c.designation, c.no_of_workers,
			c.working_hours, c.ot_hours, c.item_group
		FROM `tabProject Manpower Crew` c
		INNER JOIN `tabProject` p ON p.name = c.parent
		WHERE c.parenttype = 'Project' AND p.status = 'Open'
			AND (c.from_date IS NULL OR c.from_date <= %(date)s)
			AND (c.to_date IS NULL OR c.to_date >= %(date)s)
		ORDER BY c.parent, c.idx
		""",
		{"date": date},
		as_dict=True,
	)
	if not crews:
		return [], []

	# crews already booked (same project, agency and trade) on this date
	booked = {
		(r.project, r.supplier, r.designation or "")
		for r in frappe.db.sql(
			"""
			SELECT me.project, d.supplier, d.designation FROM `tabManpower Entry Detail` d
			INNER JOIN `tabManpower Entry` me ON me.name = d.parent
			WHERE me.docstatus < 2 AND me.posting_date = %s AND IFNULL(d.employee, '') = ''
			""",
			date,
			as_dict=True,
		)
	}
	skip_holidays = cint(settings.get("skip_holidays_for_crews"))
	rows, skipped, holiday_cache = [], [], {}
	for c in crews:
		if skip_holidays and _is_holiday(c.company, date, holiday_cache):
			continue
		if (c.project, c.supplier, c.designation or "") in booked:
			continue
		hours = flt(c.working_hours) if c.working_hours is not None else 8
		if hours <= 0 and flt(c.ot_hours) <= 0:
			continue
		hourly, ot_rate = resolve_rates(OUTSOURCED, c.supplier, c.designation)
		if not hourly:
			skipped.append(_("{0} crew on {1}: no agency rate").format(c.supplier, c.project))
			continue
		rows.append(
			(
				c.project,
				{
					"worker_type": OUTSOURCED,
					"supplier": c.supplier,
					"designation": c.designation,
					"no_of_workers": cint(c.no_of_workers) or 1,
					"working_hours": hours,
					"ot_hours": flt(c.ot_hours),
					"hourly_rate": hourly,
					"ot_hourly_rate": ot_rate,
					"item_group": c.item_group,
				},
			)
		)
	return rows, skipped

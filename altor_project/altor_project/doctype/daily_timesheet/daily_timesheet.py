# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Daily Timesheet: one date, many employees (a crew sheet).

On submit each employee gets a standard ERPNext Timesheet for the date (their rows, one after the
other), so labour cost, overtime, the project budget and the reports work as before. Cancelling the
Daily Timesheet cancels those Timesheets.
"""

from collections import OrderedDict
from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, get_link_to_form, getdate, to_timedelta

DAY_START = time(8, 0)


class DailyTimesheet(Document):
	# the Timesheets made from this sheet are cancelled with it (on_cancel)
	ignore_linked_doctypes = ("Timesheet",)

	def validate(self):
		self.set_rows()
		self.set_totals()

	def before_submit(self):
		missing = [str(row.idx) for row in self.time_logs if not row.activity_type]
		if missing:
			frappe.throw(
				_("Activity Type is needed on rows {0}: set a Default Activity Type or one per row.").format(
					", ".join(missing)
				)
			)

	def on_submit(self):
		self.make_timesheets()

	def on_cancel(self):
		self.cancel_timesheets()

	# ------------------------------------------------------------------ validation

	def set_rows(self):
		if not self.time_logs:
			frappe.throw(_("Add the employees who worked on {0}.").format(frappe.format(self.date, "Date")))
		employees = {
			e.name: e
			for e in frappe.get_all(
				"Employee",
				filters={"name": ["in", list({r.employee for r in self.time_logs if r.employee})]},
				fields=["name", "employee_name", "status", "company", "custom_is_outsourced"]
				if frappe.get_meta("Employee").has_field("custom_is_outsourced")
				else ["name", "employee_name", "status", "company"],
			)
		}
		for row in self.time_logs:
			emp = employees.get(row.employee)
			if not emp:
				frappe.throw(_("Row #{0}: select the employee.").format(row.idx))
			if emp.status != "Active":
				frappe.throw(_("Row #{0}: {1} is not an active employee.").format(row.idx, emp.employee_name))
			if self.company and emp.company and emp.company != self.company:
				frappe.throw(
					_("Row #{0}: {1} belongs to {2}, not {3}.").format(
						row.idx, emp.employee_name, emp.company, self.company
					)
				)
			row.employee_name = emp.employee_name
			row.worker_type = _("Outsourced") if cint(emp.get("custom_is_outsourced")) else _("Own Staff")
			row.project = row.project or self.project
			if not row.project:
				frappe.throw(_("Row #{0}: select the project (or a project at the top).").format(row.idx))
			row.activity_type = row.activity_type or self.activity_type
			if flt(row.hours) <= 0:
				frappe.throw(_("Row #{0}: enter the hours worked.").format(row.idx))
			if cint(self.auto_overtime):
				row.ot1_hours = row.ot2_hours = 0
			elif flt(row.ot1_hours) + flt(row.ot2_hours) > flt(row.hours):
				frappe.throw(
					_("Row #{0}: OT 1 + OT 2 hours cannot be more than the hours worked.").format(row.idx)
				)

	def set_totals(self):
		self.total_employees = len({row.employee for row in self.time_logs})
		self.total_hours = flt(sum(flt(row.hours) for row in self.time_logs), 2)

	# ------------------------------------------------------------------ timesheets

	def make_timesheets(self):
		by_employee = OrderedDict()
		for row in self.time_logs:
			by_employee.setdefault(row.employee, []).append(row)
		auto = cint(self.auto_overtime)
		total = 0
		for employee, rows in by_employee.items():
			start = first_free_time(employee, self.date)
			ts = frappe.new_doc("Timesheet")
			ts.update({"company": self.company, "employee": employee, "start_date": self.date})
			if ts.meta.has_field("custom_auto_overtime"):
				ts.custom_auto_overtime = auto
			if ts.meta.has_field("custom_daily_timesheet"):
				ts.custom_daily_timesheet = self.name
			for row in rows:
				from_time = start
				if row.from_time:
					from_time = datetime.combine(getdate(self.date), time()) + to_timedelta(row.from_time)
				log = {
					"activity_type": row.activity_type,
					"from_time": from_time,
					"hours": flt(row.hours),
					"to_time": from_time + timedelta(hours=flt(row.hours)),
					"project": row.project,
					"task": row.task,
					"description": row.description,
				}
				if not auto:
					log.update(custom_ot1_hours=flt(row.ot1_hours), custom_ot2_hours=flt(row.ot2_hours))
				ts.append("time_logs", log)
				start = max(start, log["to_time"])
			ts.flags.ignore_permissions = True  # the user may submit this Daily Timesheet
			ts.insert()
			ts.submit()
			for row, log in zip(rows, ts.time_logs, strict=True):
				row.db_set("timesheet", ts.name, update_modified=False)
				row.db_set("labour_cost", flt(log.get("custom_labour_cost"), 2), update_modified=False)
			total += flt(ts.get("custom_total_labour_cost") or ts.get("total_costing_amount"))
		self.db_set("total_labour_cost", flt(total, 2), update_modified=False)
		frappe.msgprint(
			_("{0} Timesheets made: {1}").format(
				len(by_employee),
				", ".join(
					get_link_to_form("Timesheet", n)
					for n in dict.fromkeys(r.timesheet for r in self.time_logs)
				),
			),
			alert=True,
			indicator="green",
		)

	def cancel_timesheets(self):
		for name in dict.fromkeys(row.timesheet for row in self.time_logs if row.timesheet):
			ts = frappe.get_doc("Timesheet", name)
			if ts.docstatus == 1:
				ts.flags.ignore_permissions = True
				ts.cancel()


def first_free_time(employee, date):
	"""08:00 on the date, or the end of the employee's last hours already booked that day."""
	start = datetime.combine(getdate(date), DAY_START)
	latest = frappe.db.sql(
		"""
		SELECT MAX(td.to_time)
		FROM `tabTimesheet Detail` td
		INNER JOIN `tabTimesheet` ts ON ts.name = td.parent
		WHERE ts.employee = %s AND ts.docstatus < 2 AND DATE(td.from_time) = %s
		""",
		(employee, getdate(date)),
	)[0][0]
	return max(start, get_datetime(latest)) if latest else start

# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from altor_project.manpower import (
	OUTSOURCED,
	OWN,
	get_employees,
	get_settings,
	missing_rate_message,
	resolve_rates,
)

MAX_HOURS_PER_DAY = 24


class ManpowerEntry(Document):
	def validate(self):
		if not self.item_group:
			self.item_group = get_settings().item_group
		self.validate_project()
		self.set_row_details()
		self.validate_rows()
		self.validate_daily_hours()
		self.calculate_totals()

	def on_submit(self):
		self.update_budget()

	def on_cancel(self):
		self.update_budget()

	def update_budget(self):
		from altor_project.budget import queue_budget_update

		queue_budget_update(self.project)

	def validate_project(self):
		status = frappe.db.get_value("Project", self.project, "status")
		if status in ("Completed", "Cancelled"):
			frappe.throw(
				_("Project {0} is {1}. Manpower can only be booked on open projects.").format(
					frappe.bold(self.project), _(status)
				)
			)

	def set_row_details(self):
		employees = get_employees([d.employee for d in self.details])
		for d in self.details:
			emp = employees.get(d.employee) if d.employee else None
			if emp:
				d.worker_type = OUTSOURCED if emp.get("custom_is_outsourced") else OWN
				d.employee_name = emp.employee_name
				d.designation = d.designation or emp.designation
				if d.worker_type == OUTSOURCED:
					d.supplier = emp.get("custom_manpower_supplier") or d.supplier
				d.no_of_workers = 1
			if d.worker_type == OWN:
				d.supplier = None
			if not flt(d.hourly_rate) or (flt(d.ot_hours) and not flt(d.ot_hourly_rate)):
				hourly, ot = resolve_rates(d.worker_type, d.supplier, d.designation, emp)
				d.hourly_rate = flt(d.hourly_rate) or hourly
				d.ot_hourly_rate = flt(d.ot_hourly_rate) or ot
			d.no_of_workers = d.no_of_workers if d.no_of_workers is not None else 1
			d.amount = flt(
				(d.no_of_workers or 0)
				* (flt(d.working_hours) * flt(d.hourly_rate) + flt(d.ot_hours) * flt(d.ot_hourly_rate)),
				2,
			)

	def validate_rows(self):
		if not self.details:
			frappe.throw(_("Add at least one worker row."))
		seen, inactive, no_rate = {}, [], []
		for d in self.details:
			if d.worker_type == OWN and not d.employee:
				frappe.throw(_("Row #{0}: Select the Employee for own staff.").format(d.idx))
			if d.worker_type == OUTSOURCED and not d.supplier:
				frappe.throw(
					_("Row #{0}: Manpower Supplier is mandatory for outsourced workers.").format(d.idx)
				)
			if (d.no_of_workers or 0) < 1:
				frappe.throw(_("Row #{0}: Workers must be at least 1.").format(d.idx))
			if flt(d.working_hours) < 0 or flt(d.ot_hours) < 0:
				frappe.throw(_("Row #{0}: Hours cannot be negative.").format(d.idx))
			if not flt(d.working_hours) and not flt(d.ot_hours):
				frappe.throw(_("Row #{0}: Enter Hours or OT Hours.").format(d.idx))
			if flt(d.working_hours) + flt(d.ot_hours) > MAX_HOURS_PER_DAY:
				frappe.throw(
					_("Row #{0}: Hours + OT Hours cannot be more than {1}.").format(d.idx, MAX_HOURS_PER_DAY)
				)
			if d.employee:
				if d.employee in seen:
					frappe.throw(
						_("Row #{0}: Employee {1} is already in row #{2}.").format(
							d.idx, frappe.bold(d.employee_name or d.employee), seen[d.employee]
						)
					)
				seen[d.employee] = d.idx
			if not flt(d.amount):
				no_rate.append(d)

		if no_rate:
			frappe.throw(missing_rate_message(no_rate), title=_("Rate Missing"))

		if seen:
			inactive = frappe.get_all(
				"Employee", filters={"name": ["in", list(seen)], "status": ["!=", "Active"]}, pluck="name"
			)
			if inactive:
				frappe.msgprint(
					_("These employees are not Active: {0}").format(", ".join(inactive)),
					indicator="orange",
					title=_("Warning"),
				)

	def validate_daily_hours(self):
		"""An employee cannot be booked for more than 24 hours on one day across all projects."""
		employees = {d.employee: flt(d.working_hours) + flt(d.ot_hours) for d in self.details if d.employee}
		if not employees:
			return
		booked = frappe.db.sql(
			"""
			SELECT d.employee, SUM(IFNULL(d.working_hours, 0) + IFNULL(d.ot_hours, 0)) AS hours,
				GROUP_CONCAT(DISTINCT me.name) AS entries
			FROM `tabManpower Entry Detail` d
			INNER JOIN `tabManpower Entry` me ON me.name = d.parent
			WHERE me.docstatus < 2 AND me.posting_date = %(date)s AND me.name != %(name)s
				AND d.employee IN %(employees)s
			GROUP BY d.employee
			""",
			{"date": self.posting_date, "name": self.name or "", "employees": tuple(employees)},
			as_dict=True,
		)
		for b in booked:
			total = flt(b.hours) + employees[b.employee]
			if total > MAX_HOURS_PER_DAY:
				frappe.throw(
					_("Employee {0} would be booked for {1} hours on {2} (already in {3}).").format(
						frappe.bold(b.employee), total, frappe.format(self.posting_date, "Date"), b.entries
					),
					title=_("Too Many Hours"),
				)
			frappe.msgprint(
				_("Employee {0} is also booked on {1} in {2}.").format(
					frappe.bold(b.employee), frappe.format(self.posting_date, "Date"), b.entries
				),
				indicator="orange",
				title=_("Warning"),
			)

	def calculate_totals(self):
		self.total_workers = sum(d.no_of_workers or 0 for d in self.details)
		self.total_hours = sum(flt(d.working_hours) * (d.no_of_workers or 0) for d in self.details)
		self.total_ot_hours = sum(flt(d.ot_hours) * (d.no_of_workers or 0) for d in self.details)
		self.own_staff_cost = sum(flt(d.amount) for d in self.details if d.worker_type == OWN)
		self.outsourced_cost = sum(flt(d.amount) for d in self.details if d.worker_type == OUTSOURCED)
		self.total_cost = self.own_staff_cost + self.outsourced_cost


@frappe.whitelist()
def copy_from_previous(project, posting_date=None, exclude=None):
	"""Workers of the latest entry for the project, to repeat a daily crew quickly."""
	frappe.has_permission("Manpower Entry", "read", throw=True)
	filters = {"project": project, "docstatus": ["<", 2]}
	if exclude:
		filters["name"] = ["!=", exclude]
	if posting_date:
		filters["posting_date"] = ["<=", posting_date]
	last = frappe.get_all(
		"Manpower Entry", filters=filters, order_by="posting_date desc, creation desc", limit=1, pluck="name"
	)
	if not last:
		return []
	fields = [
		"worker_type",
		"employee",
		"employee_name",
		"supplier",
		"designation",
		"no_of_workers",
		"working_hours",
		"ot_hours",
		"hourly_rate",
		"ot_hourly_rate",
		"amount",
		"item_group",
	]
	return frappe.get_all(
		"Manpower Entry Detail",
		filters={"parent": last[0], "parenttype": "Manpower Entry"},
		fields=fields,
		order_by="idx asc",
	)

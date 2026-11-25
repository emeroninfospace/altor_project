import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from altor_project.custom_and_property_setter.custom_field import CREATE_FIELDS


def execute():
	"""Crew Timesheet: an Employee per row (several employees and projects on one Timesheet).

	ERPNext's user overlap check compares every row of a Timesheet made without an Employee, so a crew
	working the same hours would be refused; overlaps are checked per employee instead (employee
	overlap stays on, plus altor_project.labour.validate_employee_overlap for the rows)."""
	create_custom_fields(
		{"Timesheet Detail": CREATE_FIELDS["Timesheet Detail"]}, ignore_validate=True, update=True
	)
	frappe.db.set_single_value("Projects Settings", "ignore_user_time_overlap", 1)

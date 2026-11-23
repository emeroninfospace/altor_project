from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from altor_project.custom_and_property_setter.custom_field import CREATE_FIELDS


def execute():
	"""Timesheet > Daily Timesheet: the crew sheet a Timesheet was made from."""
	create_custom_fields({"Timesheet": CREATE_FIELDS["Timesheet"]}, ignore_validate=True, update=True)

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from altor_project.custom_and_property_setter.custom_field import CREATE_FIELDS
from altor_project.custom_and_property_setter.settings_defaults import apply_single_defaults


def execute():
	"""Timesheet labour cost (normal / OT 1 / OT 2) and own staff salary fields."""
	create_custom_fields(
		{dt: CREATE_FIELDS[dt] for dt in ("Employee", "Timesheet", "Timesheet Detail")},
		ignore_validate=True,
		update=True,
	)
	apply_single_defaults("Altor Settings")

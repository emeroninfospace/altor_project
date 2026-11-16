from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from altor_project.custom_and_property_setter.custom_field import CREATE_FIELDS


def execute():
	"""Employee Manpower Costing: outsourced = hourly charge only, own staff = salary only."""
	create_custom_fields({"Employee": CREATE_FIELDS["Employee"]}, ignore_validate=True, update=True)

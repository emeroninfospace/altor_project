from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from altor_project.custom_and_property_setter.custom_field import CREATE_FIELDS


def execute():
	"""Item: the Project Asset description says Fixed Asset."""
	create_custom_fields({"Item": CREATE_FIELDS["Item"]}, ignore_validate=True, update=True)

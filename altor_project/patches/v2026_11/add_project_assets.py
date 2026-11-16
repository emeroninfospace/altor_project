from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from altor_project.custom_and_property_setter.custom_field import CREATE_FIELDS


def execute():
	"""Item / GRN fields for Project Assets (asset allocation to projects)."""
	create_custom_fields(
		{dt: CREATE_FIELDS[dt] for dt in ("Item", "Purchase Receipt Item")},
		ignore_validate=True,
		update=True,
	)

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from altor_project.custom_and_property_setter.custom_field import CREATE_FIELDS
from altor_project.custom_and_property_setter.settings_defaults import apply_single_defaults


def execute():
	"""Project Assets link to ERPNext Assets: the depreciation period now comes from the Asset Category."""
	for doctype in ("Item", "Purchase Receipt Item"):
		for name in frappe.get_all(
			"Custom Field", filters={"dt": doctype, "fieldname": "custom_depreciation_months"}, pluck="name"
		):
			frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)
	create_custom_fields(
		{dt: CREATE_FIELDS[dt] for dt in ("Item", "Journal Entry")}, ignore_validate=True, update=True
	)
	apply_single_defaults("Altor Settings")

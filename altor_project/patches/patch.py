import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from altor_project.custom_and_property_setter.custom_field import CREATE_FIELDS
from altor_project.custom_and_property_setter.property_setter import get_property_setters
from altor_project.setup import after_install


def execute():

	create_custom_fields(CREATE_FIELDS, ignore_validate=True)
	make_property_setters()


def make_property_setters():
	for property_setter in get_property_setters():
		frappe.make_property_setter(property_setter, validate_fields_for_doctype=False)

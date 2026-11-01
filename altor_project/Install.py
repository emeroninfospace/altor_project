from __future__ import unicode_literals
import frappe
from altor_project.custom_and_property_setter.property_setter import get_property_setters
from frappe.custom.doctype.property_setter.property_setter import  make_property_setter


def after_migrate():
    make_property_setters()

def make_property_setters():
    for property_setter in get_property_setters():
        frappe.make_property_setter(property_setter, validate_fields_for_doctype=False)
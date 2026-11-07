# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Remove Bill of Quantity (BOQ) and introduce Division (= Cost Center).

* Keep data of renamed fields: Project Budget Item boq_amount -> quoted_amount,
  Project Schedule Child boq_template -> work_package.
* Leads on "Bill of Quantity Completed" go back to "Site Visit Completed" / "Open".
* Delete BOQ custom fields, property setters, print formats and doctypes
  (Bill of Quantity, Bill of Quantity Item, BOQ Template Child, BOQ Items) with their records.
* Add / relabel the Division field on the flow documents.
"""

import frappe

from altor_project.custom_and_property_setter.custom_field import CREATE_FIELDS
from altor_project.custom_and_property_setter.division import setup_division_fields

BOQ_DOCTYPES = ["Bill of Quantity", "Bill of Quantity Item", "BOQ Template Child", "BOQ Items"]
BOQ_FIELDNAMES = ["custom_bill_of_quantity", "custom_boq_items", "custom_show_boq_items", "custom_show_boq_template_title"]
BOQ_PRINT_FORMATS = ["Boq", "Bill of Quantity"]


def execute():
	copy_column("Project Budget Item", "boq_amount", "quoted_amount")
	copy_column("Project Schedule Child", "boq_template", "work_package")
	reset_lead_status()
	delete_boq_customizations()
	delete_boq_print_formats()
	delete_boq_doctypes()

	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(CREATE_FIELDS, ignore_validate=True)  # re-anchors fields that sat after BOQ fields
	setup_division_fields()


def copy_column(doctype, old, new):
	if frappe.db.has_column(doctype, old) and frappe.db.has_column(doctype, new):
		frappe.db.sql(
			f"UPDATE `tab{doctype}` SET `{new}` = `{old}` WHERE (`{new}` IS NULL OR `{new}` = '' OR `{new}` = 0) AND `{old}` IS NOT NULL"
		)


def reset_lead_status():
	for lead in frappe.get_all("Lead", filters={"status": "Bill of Quantity Completed"}, pluck="name"):
		visited = frappe.db.exists("Site Visit", {"lead": lead, "docstatus": 1})
		frappe.db.set_value("Lead", lead, "status", "Site Visit Completed" if visited else "Open", update_modified=False)


def delete_boq_customizations():
	fields = frappe.get_all(
		"Custom Field",
		or_filters=[
			["fieldname", "in", BOQ_FIELDNAMES],
			["options", "in", BOQ_DOCTYPES],
			["label", "in", ["BOQ Items", "Bill of Quantity"]],
		],
		pluck="name",
	)
	for name in fields:
		frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)
	for name in frappe.get_all(
		"Property Setter",
		or_filters=[["field_name", "in", BOQ_FIELDNAMES], ["doc_type", "in", BOQ_DOCTYPES]],
		pluck="name",
	):
		frappe.delete_doc("Property Setter", name, force=True, ignore_permissions=True)
	# a default print format that pointed at a BOQ format
	for ps in frappe.get_all(
		"Property Setter",
		filters={"doc_type": "Quotation", "property": "default_print_format"},
		fields=["name", "value"],
	):
		if ps.value in BOQ_PRINT_FORMATS or "boq" in (ps.value or "").lower():
			frappe.db.set_value("Property Setter", ps.name, "value", "Quotation")


def delete_boq_print_formats():
	for name in BOQ_PRINT_FORMATS:
		if frappe.db.exists("Print Format", name) and frappe.db.get_value("Print Format", name, "module") == "Altor Project":
			frappe.delete_doc("Print Format", name, force=True, ignore_permissions=True)


def delete_boq_doctypes():
	for doctype in BOQ_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.get_value("DocType", doctype, "istable"):
			frappe.db.delete(doctype)  # records (child rows go with their table)
		frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True, ignore_missing=True)
	frappe.clear_cache()

# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Remove Manpower Entry: labour is costed on Timesheets now (altor_project.labour).

* Delete Manpower Entry, Manpower Entry Detail, Project Manpower Crew and Manpower Rate
  with their records, and the Altor Manpower Sheet print format.
* Delete the custom fields that only served them (Project Daily Manpower Crew, Employee
  OT Hourly Rate / Assigned Project, Employee Checkin Project) and the old automation
  settings of Altor Settings.
"""

import frappe

DOCTYPES = ["Manpower Entry", "Manpower Entry Detail", "Project Manpower Crew", "Manpower Rate"]
FIELDS = {
	"Project": ["custom_manpower_crew_section", "custom_manpower_crew"],
	"Employee": ["custom_ot_hourly_rate", "custom_current_project"],
	"Employee Checkin": ["custom_project"],
}
PRINT_FORMATS = ["Altor Manpower Sheet"]
SETTINGS = [
	"manpower_rates",
	"auto_create_manpower_entries",
	"manpower_entry_source",
	"auto_submit_manpower_entries",
	"skip_holidays_for_crews",
	"working_days_per_month",
]


def execute():
	for doctype, fieldnames in FIELDS.items():
		for name in frappe.get_all(
			"Custom Field", filters={"dt": doctype, "fieldname": ["in", fieldnames]}, pluck="name"
		):
			frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)
	for name in frappe.get_all(
		"Property Setter",
		or_filters=[
			["doc_type", "in", DOCTYPES],
			["field_name", "in", [f for fields in FIELDS.values() for f in fields]],
		],
		pluck="name",
	):
		frappe.delete_doc("Property Setter", name, force=True, ignore_permissions=True)

	for name in PRINT_FORMATS:
		if frappe.db.exists("Print Format", name):
			frappe.delete_doc("Print Format", name, force=True, ignore_permissions=True)

	for doctype in DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.get_value("DocType", doctype, "istable"):
			frappe.db.delete(doctype)  # records (child rows go with their table)
		frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True, ignore_missing=True)

	frappe.db.delete("Singles", {"doctype": "Altor Settings", "field": ["in", SETTINGS]})
	frappe.db.delete("Scheduled Job Type", {"method": ["like", "altor_project.manpower_automation.%"]})
	frappe.clear_cache()

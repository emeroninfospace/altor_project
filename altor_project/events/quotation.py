import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import date_diff, flt, nowdate


@frappe.whitelist()
def make_project(source_name, target_doc=None):
	"""Create Project from Quotation"""

	def set_missing_values(source, target):
		if source.quotation_to == "Lead":
			customer_name = frappe.db.get_value("Customer", {"customer_name": source.customer_name}, "name")
			if not customer_name:
				customer = frappe.get_doc(
					{
						"doctype": "Customer",
						"customer_name": source.customer_name,
						"customer_type": "Individual",
						"customer_group": frappe.db.get_default("customer_group") or "All Customer Groups",
						"territory": frappe.db.get_default("territory") or "All Territories",
					}
				)
				customer.flags.ignore_permissions = True
				customer.insert()
				customer_name = customer.name
		else:
			customer_name = source.party_name

		target.customer = customer_name
		target.quotation = source.name

	doclist = get_mapped_doc(
		"Quotation",
		source_name,
		{
			"Quotation": {
				"doctype": "Project",
				"field_map": {
					"custom_project": "project_name",
					"remarks": "notes",
					"custom_scope_of_work": "scope_of_work",
					"custom_location": "location",
				},
			}
		},
		target_doc,
		set_missing_values,
	)

	return doclist


@frappe.whitelist()
def make_sales_invoice(source_name, target_doc=None):

	def set_missing_values(source, target):
		if source.quotation_to == "Lead":
			lead_id = source.party_name
			customer_name = frappe.db.get_value("Customer", {"lead_name": lead_id}, "name")
			if not customer_name:
				customer = frappe.get_doc(
					{
						"doctype": "Customer",
						"customer_name": source.customer_name,
						"customer_type": "Individual",
						"lead_name": lead_id,
						"customer_group": frappe.db.get_default("customer_group") or "All Customer Groups",
						"territory": frappe.db.get_default("territory") or "All Territories",
					}
				)
				customer.flags.ignore_permissions = True
				customer.insert()
				customer_name = customer.name
		else:
			customer_name = source.party_name

		target.posting_date = nowdate()
		target.customer = customer_name
		target.remarks = f"Sales Invoice created from Quotation {source.name}"

		default_income_account = frappe.get_cached_value("Company", source.company, "default_income_account")
		for item in target.items:
			income_account = frappe.db.get_value(
				"Item Default", {"parent": item.item_code, "company": source.company}, "income_account"
			)
			item.income_account = income_account or default_income_account

	doclist = get_mapped_doc(
		"Quotation",
		source_name,
		{
			"Quotation": {
				"doctype": "Sales Invoice",
				"field_map": {
					"name": "custom_quotation",
				},
			},
			"Quotation Item": {
				"doctype": "Sales Invoice Item",
				"field_map": {
					"item_code": "item_code",
					"item_name": "item_name",
					"qty": "qty",
					"rate": "rate",
					"amount": "amount",
					"uom": "uom",
					"description": "description",
				},
			},
		},
		target_doc,
		set_missing_values,
	)

	return doclist


import re

import frappe
from erpnext.selling.doctype.quotation.quotation import Quotation


class CustomQuotation(Quotation):
	def after_insert(self):
		if self.amended_from:
			base_name = re.sub(r"-R\d+$", "", self.amended_from)
			base_name = re.sub(r"-(\d{1,2})$", "", base_name)

			existing = frappe.db.sql(
				"""
                SELECT COUNT(*) FROM `tabQuotation`
                WHERE name LIKE %s
            """,
				(f"{base_name}-R%",),
			)[0][0]

			new_name = f"{base_name}-R{existing + 1}"

			frappe.rename_doc("Quotation", self.name, new_name, force=True)
			self.name = new_name
			self.amended_from = self.amended_from
			self.reload()

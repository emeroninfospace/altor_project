import re

import frappe
from erpnext.selling.doctype.quotation.quotation import Quotation
from frappe import _
from frappe.utils import cint

from altor_project.events.lead import customer_of_lead


def lead_required():
	"""Altor Settings > Quotation Only for a Lead (on unless switched off)."""
	value = frappe.get_cached_doc("Altor Settings").get("quotation_for_lead_only")
	return 1 if value is None else cint(value)


def require_lead(doc, method=None):
	"""doc_event (Quotation validate): quotations are made for a Lead (an existing customer gets a
	Lead with its Existing Customer set)."""
	if doc.flags.ignore_lead_check or doc.quotation_to == "Lead" or not lead_required():
		return
	frappe.throw(
		_(
			"A Quotation is made for a Lead. For an existing customer, create a Lead, choose the customer in Existing Customer, then Create > Quotation on the Lead."
		),
		title=_("Lead Required"),
	)


@frappe.whitelist()
def make_sales_order(source_name, target_doc=None, args=None):
	"""Quotation > Create > Sales Order (replaces ERPNext's): a lead with an Existing Customer is
	ordered on that customer instead of a new customer made from the lead."""
	from erpnext.selling.doctype.quotation.quotation import make_sales_order as erpnext_make_sales_order

	quotation = frappe.db.get_value("Quotation", source_name, ["quotation_to", "party_name"], as_dict=True)
	if quotation and quotation.quotation_to == "Lead":
		customer_of_lead(quotation.party_name, link=True)
	return erpnext_make_sales_order(source_name, target_doc, args)


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

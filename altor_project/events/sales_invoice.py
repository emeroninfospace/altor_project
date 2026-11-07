import frappe
from erpnext.crm.doctype.lead.lead import _make_customer


def on_submit(doc, method=None):
	if doc.custom_quotation:
		_set_quotation_status(doc.custom_quotation, "Ordered")
		_convert_lead_to_customer(doc.custom_quotation)


def on_cancel(doc, method=None):
	if not doc.custom_quotation:
		return

	active_invoice_exists = frappe.db.exists(
		"Sales Invoice", {"quotation": doc.custom_quotation, "docstatus": 1, "name": ["!=", doc.name]}
	)

	if not active_invoice_exists:
		_set_quotation_status(doc.custom_quotation, "Open")


def _set_quotation_status(quotation_name, status):
	quotation = frappe.get_doc("Quotation", quotation_name)

	if quotation.docstatus != 1:
		return

	if quotation.status in ("Lost", "Closed"):
		return

	if quotation.status != status:
		quotation.db_set("status", status, update_modified=False)


def _convert_lead_to_customer(quotation_name):
	quotation = frappe.db.get_value("Quotation", quotation_name, ["quotation_to", "party_name"], as_dict=True)

	if not quotation or quotation.quotation_to != "Lead" or not quotation.party_name:
		return

	lead_name = quotation.party_name

	existing_customer = frappe.db.get_value("Customer", {"lead_name": lead_name}, "name")
	if existing_customer:
		return

	customer_doc = _make_customer(lead_name, ignore_permissions=True)
	customer_doc.flags.ignore_mandatory = True
	customer_doc.insert(ignore_permissions=True)

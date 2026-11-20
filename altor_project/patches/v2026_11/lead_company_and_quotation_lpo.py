import frappe
from frappe.modules.utils import sync_customizations


def execute():
	"""Lead: First Name is the Company Name, the person goes in Contact Name. Quotation: no LPO fields.
	Sales Order: only from a Quotation."""
	sync_customizations("altor_project")  # adds Lead > Contact Name before the leads are moved

	# Sales Orders only from a Quotation (new setting, on)
	frappe.db.set_single_value("Altor Settings", "sales_order_from_quotation_only", 1)

	# the client's LPO is recorded on the Sales Order / Project, not on the Quotation
	for fieldname in ("lpo_ref", "lpo_date"):
		name = frappe.db.get_value("Custom Field", {"dt": "Quotation", "fieldname": fieldname})
		if name:
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)

	# leads saved with the person in First Name and the company in Organization Name
	for lead in frappe.get_all(
		"Lead",
		filters={"company_name": ["is", "set"]},
		fields=["name", "first_name", "middle_name", "last_name", "company_name", "custom_contact_name"],
	):
		if lead.first_name == lead.company_name:
			continue
		person = " ".join(filter(None, [lead.first_name, lead.middle_name, lead.last_name]))
		frappe.db.set_value(
			"Lead",
			lead.name,
			{
				"custom_contact_name": lead.custom_contact_name or person,
				"first_name": lead.company_name,
				"middle_name": None,
				"last_name": None,
				"lead_name": lead.company_name,
				"title": lead.company_name,
			},
			update_modified=False,
		)

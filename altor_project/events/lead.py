import frappe


def update_lead_status(lead_name, status):
	if not lead_name:
		return
	current_status = frappe.db.get_value("Lead", lead_name, "status")
	if current_status and current_status != status:
		frappe.db.set_value("Lead", lead_name, "status", status, update_modified=False)


def on_site_visit_submit(doc, method=None):
	update_lead_status(doc.lead, "Site Visit Completed")

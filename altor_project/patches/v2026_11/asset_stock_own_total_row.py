import frappe


def execute():
	"""Project Asset Stock adds its own total row (the average columns are not added up).

	Frappe keeps a site's "Add Total Row" when it syncs a standard report, so switch it off here."""
	if frappe.db.exists("Report", "Project Asset Stock"):
		frappe.db.set_value("Report", "Project Asset Stock", "add_total_row", 0, update_modified=False)

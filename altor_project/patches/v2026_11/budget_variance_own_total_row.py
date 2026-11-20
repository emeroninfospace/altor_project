import frappe


def execute():
	"""Project Budget Variance adds its own total row (Utilization % = utilized / budget).

	Frappe keeps a site's "Add Total Row" when it syncs a standard report, so switch it off here."""
	if frappe.db.exists("Report", "Project Budget Variance"):
		frappe.db.set_value("Report", "Project Budget Variance", "add_total_row", 0, update_modified=False)

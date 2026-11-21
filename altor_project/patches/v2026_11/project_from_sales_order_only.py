import frappe


def execute():
	"""Projects only from a Sales Order (new Altor Settings switch, on)."""
	frappe.db.set_single_value("Altor Settings", "project_from_sales_order_only", 1)

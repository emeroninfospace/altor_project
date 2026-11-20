import frappe


def execute():
	"""Quotations only for a Lead (new Altor Settings switch, on)."""
	frappe.db.set_single_value("Altor Settings", "quotation_for_lead_only", 1)

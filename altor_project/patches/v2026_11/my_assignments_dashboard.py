import frappe


def execute():
	"""The Task Dashboard block is replaced by My Assignments (fixtures add records, they do not delete)."""
	if frappe.db.exists("Custom HTML Block", "Task Dashboard"):
		frappe.delete_doc("Custom HTML Block", "Task Dashboard", ignore_permissions=True, force=True)

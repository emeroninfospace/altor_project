import frappe


def get_permission_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	user_roles = frappe.get_roles(user)

	if "System Manager" in user_roles or "Projects Manager" in user_roles:
		return ""

	if "Projects User" in user_roles or "Supervisor" in user_roles:
		# own tasks and tasks assigned to the user (Assigned To)
		escaped = frappe.db.escape(user)
		return f"""(
			`tabTask`.`owner` = {escaped}
			OR JSON_CONTAINS(IFNULL(NULLIF(`tabTask`.`_assign`, ''), '[]'), JSON_QUOTE({escaped}), '$')
		)"""

	return ""

import json

import frappe

# def has_permission(doc, ptype='read', user=None):
# 	if not user:
# 		user = frappe.session.user

# 	if user == 'Administrator':
# 		return True

# 	user_roles = frappe.get_roles(user)

# 	if 'System Manager' in user_roles or 'Projects Manager' in user_roles:
# 		return True

# 	if ptype in ('write', 'create', 'delete', 'submit', 'cancel', 'amend'):
# 		return True

# 	if 'Projects User' in user_roles or 'Supervisor' in user_roles:

# 		if doc.owner == user:
# 			return True

# 		assign_raw = frappe.db.get_value('Task', doc.name, '_assign')
# 		assigned_to = []
# 		if assign_raw:
# 			try:
# 				assigned_to = json.loads(assign_raw) or []
# 			except Exception:
# 				assigned_to = []

# 		if user in assigned_to:
# 			return True

# 		return False

# 	return True


def get_permission_query_conditions(user=None):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	user_roles = frappe.get_roles(user)

	if "System Manager" in user_roles or "Projects Manager" in user_roles:
		return ""

	if "Projects User" in user_roles or "Supervisor" in user_roles:
		return f"""(
			`tabTask`.`owner` = '{user}'
			OR JSON_CONTAINS(`tabTask`.`_assign`, '"{user}"', '$')
		)"""

	return ""

from frappe import _


def get_data():
	return {
		"fieldname": "custom_project_schedule",
		"transactions": [{"label": _("Tasks"), "items": ["Task"]}],
	}

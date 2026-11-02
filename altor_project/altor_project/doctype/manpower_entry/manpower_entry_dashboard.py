from frappe import _


def get_data():
	return {
		"fieldname": "amended_from",
		"internal_links": {"Project": ["project"], "Task": ["task"]},
		"transactions": [
			{"label": _("Project"), "items": ["Project", "Task"]},
			{"label": _("Amendments"), "items": ["Manpower Entry"]},
		],
	}

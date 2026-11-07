from frappe import _


def get_data():
	return {
		"fieldname": "amended_from",
		"internal_links": {"Project": "project"},
		"transactions": [
			{"label": _("Project"), "items": ["Project"]},
			{"label": _("Amendments"), "items": ["Project Budget"]},
		],
	}

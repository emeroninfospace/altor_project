from frappe import _


def get_data():
	return {
		"fieldname": "site_visit",
		"internal_links": {"Lead": "lead"},
		"transactions": [
			{"label": _("Lead"), "items": ["Lead"]},
		],
	}

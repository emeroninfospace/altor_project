from frappe import _


def get_data():
	return {
		"fieldname": "amended_from",
		"internal_links": {"Journal Entry": "journal_entry", "Project": "project"},
		"transactions": [
			{"label": _("Accounting"), "items": ["Journal Entry"]},
			{"label": _("Project"), "items": ["Project"]},
		],
	}

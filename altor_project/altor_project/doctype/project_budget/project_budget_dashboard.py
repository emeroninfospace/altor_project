from frappe import _


def get_data():
	return {
		"fieldname": "amended_from",
		"internal_links": {"Project": "project", "Bill of Quantity": "boq_reference"},
		"transactions": [
			{"label": _("Project"), "items": ["Project", "Bill of Quantity"]},
			{"label": _("Amendments"), "items": ["Project Budget"]},
		],
	}

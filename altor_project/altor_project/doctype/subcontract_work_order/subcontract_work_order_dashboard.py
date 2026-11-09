from frappe import _


def get_data():
	return {
		"fieldname": "subcontract_work_order",
		"internal_links": {"Project": "project"},
		"transactions": [
			{"label": _("Billing"), "items": ["Payment Certificate", "Subcontract Invoice"]},
			{"label": _("Reference"), "items": ["Project"]},
		],
	}

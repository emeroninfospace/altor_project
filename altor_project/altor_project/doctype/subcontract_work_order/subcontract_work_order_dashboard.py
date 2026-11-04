from frappe import _


def get_data():
	return {
		"fieldname": "subcontract_work_order",
		"internal_links": {"Project": "project", "Bill of Quantity": "bill_of_quantity"},
		"transactions": [
			{"label": _("Invoices"), "items": ["Subcontract Invoice"]},
			{"label": _("Reference"), "items": ["Project", "Bill of Quantity"]},
		],
	}

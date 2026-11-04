from frappe import _


def get_data():
	return {
		"fieldname": "amended_from",
		"internal_links": {
			"Subcontract Work Order": "subcontract_work_order",
			"Project": "project",
			"Bill of Quantity": "bill_of_quantity",
		},
		"transactions": [
			{"label": _("Reference"), "items": ["Subcontract Work Order", "Project", "Bill of Quantity"]},
		],
	}

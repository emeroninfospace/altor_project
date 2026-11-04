from frappe import _


def get_data():
	return {
		"fieldname": "custom_bill_of_quantity",
		"non_standard_fieldnames": {
			"Project Schedule": "bill_of_quantity",
			"Project Budget": "boq_reference",
			"Subcontract Work Order": "bill_of_quantity",
			"Subcontract Invoice": "bill_of_quantity",
		},
		"internal_links": {"Site Visit": "site_visit"},
		"transactions": [
			{"label": _("Pre-Sales"), "items": ["Site Visit"]},
			{"label": _("Selling"), "items": ["Quotation"]},
			{"label": _("Projects"), "items": ["Project", "Project Schedule", "Project Budget", "Task"]},
			{"label": _("Subcontract"), "items": ["Subcontract Work Order", "Subcontract Invoice"]},
		],
	}

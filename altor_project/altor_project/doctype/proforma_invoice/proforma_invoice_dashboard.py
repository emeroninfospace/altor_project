from frappe import _


def get_data():
	return {
		"fieldname": "amended_from",
		"internal_links": {"Quotation": "quotation", "Sales Order": "sales_order"},
		"transactions": [
			{"label": _("Selling"), "items": ["Quotation", "Sales Order"]},
		],
	}

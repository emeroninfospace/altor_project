from frappe import _

def get_dashboard_data(data):
	return {
		"internal_links": {
			"Bill of Quantity": ["custom_bill_of_quantity"]
		},
		"transactions": [
			{
				"label": _("Bill of Quantity"),
				"items": ["Bill of Quantity"]
			},
			{
				"label": _("Selling"),
				"items": ["Sales Order", "Sales Invoice"]
			},
			{
				"label": _("Subscription"),
				"items": ["Auto Repeat"]
			},
		],
	}

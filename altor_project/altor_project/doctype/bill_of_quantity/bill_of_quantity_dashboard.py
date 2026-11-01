from frappe import _

def get_data():
	return {
		"fieldname": "custom_bill_of_quantity",

		"non_standard_fieldnames": {
			"Project Schedule": "bill_of_quantity"
		},

		"transactions": [
			{
				"label": _("Selling"),
				"items": ["Quotation"]
			},
			{
				"label": _("Projects"),
				"items": ["Project Schedule"]
			}
		]
	}

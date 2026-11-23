import frappe


def execute():
	"""Projects made from a Sales Order: the customer (ERPNext does not copy it) and the Total Sales
	Amount (left at 0 until the next save)."""
	for p in frappe.get_all(
		"Project",
		filters={"sales_order": ["is", "set"]},
		fields=["name", "sales_order", "customer", "total_sales_amount"],
	):
		so = frappe.db.get_value("Sales Order", p.sales_order, ["customer", "docstatus"], as_dict=True)
		if not so:
			continue
		values = {}
		if not p.customer and so.customer:
			values["customer"] = so.customer
		if not p.total_sales_amount:
			total = frappe.db.sql(
				"SELECT SUM(base_net_total) FROM `tabSales Order` WHERE (project = %s OR name = %s) AND docstatus = 1",
				(p.name, p.sales_order),
			)[0][0]
			if total:
				values["total_sales_amount"] = total
		if values:
			frappe.db.set_value("Project", p.name, values, update_modified=False)

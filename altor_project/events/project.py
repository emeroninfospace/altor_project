import frappe
from frappe import _
from frappe.utils import flt, nowdate


def get_project_source_items(project_doc):
	"""Items the project was sold with: its Sales Order, else its Quotation.

	Returns (source_doctype, source_name, [{item_code, item_name, item_group, uom, qty, rate, amount}]).
	"""
	sources = []
	if project_doc.get("sales_order"):
		sources.append(("Sales Order", project_doc.sales_order))
	if project_doc.get("quotation"):
		sources.append(("Quotation", project_doc.quotation))
	for doctype, name in sources:
		if not frappe.db.exists(doctype, name):
			continue
		rows = frappe.get_all(
			f"{doctype} Item",
			filters={"parent": name, "parenttype": doctype},
			fields=["item_code", "item_name", "item_group", "uom", "qty", "rate", "amount", "description"],
			order_by="idx asc",
		)
		if rows:
			return doctype, name, rows
	return None, None, []


@frappe.whitelist()
def create_project_schedule(project):
	project_doc = frappe.get_doc("Project", project)
	_doctype, _name, items = get_project_source_items(project_doc)

	ps = frappe.new_doc("Project Schedule")
	ps.project = project_doc.name
	for row in items:
		task = ps.append("project_schedule_tasks")
		task.description = row.item_name
		task.work_package = row.item_group
		task.item_code = row.item_code
	if not items:
		# Empty schedule to fill in by hand
		ps.append("project_schedule_tasks", {"description": project_doc.project_name})

	ps.insert(ignore_permissions=True)
	return ps.name


@frappe.whitelist()
def create_material_request(name):
	project = frappe.get_doc("Project", name)
	source_doctype, source_name, items = get_project_source_items(project)

	# Only stock / purchase items can be requested (not hire or service lines)
	purchasable = set()
	if items:
		purchasable = set(
			frappe.get_all(
				"Item",
				filters={"name": ["in", list({i.item_code for i in items if i.item_code})], "is_purchase_item": 1},
				pluck="name",
			)
		)
	items = [i for i in items if i.item_code in purchasable]
	if not items:
		frappe.throw(
			_("No purchasable items found on the project's Sales Order or Quotation. Create the Material Request manually.")
		)

	request = frappe.new_doc("Material Request")
	request.custom_project = name
	request.material_request_type = "Purchase"
	if project.get("cost_center") and frappe.get_meta("Material Request").has_field("cost_center"):
		request.cost_center = project.cost_center

	item_codes = list({item.item_code for item in items})
	requested = dict(
		frappe.db.sql(
			"""
			SELECT item_code, SUM(qty)
			FROM `tabMaterial Request Item`
			WHERE project = %s AND item_code IN %s AND docstatus != 2
			GROUP BY item_code
			""",
			(name, tuple(item_codes)),
		)
	)

	for item in items:
		# Quantity still to request: sold qty minus what earlier (non-cancelled) requests asked for.
		# Repeated lines for the same item share the requested quantity.
		used_qty_val = flt(requested.get(item.item_code))
		available_qty = flt(item.qty) - used_qty_val
		requested[item.item_code] = max(used_qty_val - flt(item.qty), 0)

		if available_qty > 0:
			request.append(
				"items",
				{
					"item_code": item.item_code,
					"item_name": item.item_name,
					"uom": item.uom,
					"qty": available_qty,
					"schedule_date": nowdate(),
					"project": name,
				},
			)

	if not request.items:
		frappe.throw(_("Everything on {0} {1} has already been requested.").format(_(source_doctype), source_name))

	request.save(ignore_permissions=True)
	return request.name


@frappe.whitelist()
def make_project_budget(project):
	project_doc = frappe.get_doc("Project", project)

	existing = frappe.db.get_value("Project Budget", {"project": project, "docstatus": ["<", 2]}, "name")
	if existing:
		frappe.msgprint(
			_("Project Budget {0} already exists for this project.").format(
				frappe.utils.get_link_to_form("Project Budget", existing)
			),
			indicator="orange",
		)
		return existing

	ps = frappe.new_doc("Project Budget")
	ps.project = project_doc.name

	# One budget line per Item Group of what was sold. The quoted (selling) value is kept
	# as a reference; the budgeted (cost) amount is entered by the user.
	_doctype, _name, items = get_project_source_items(project_doc)
	lines = {}
	for row in items:
		if row.item_group:
			lines[row.item_group] = lines.get(row.item_group, 0) + flt(row.amount)
	for item_group, amount in lines.items():
		ps.append("budget_items", {"category": item_group, "quoted_amount": amount})

	if not ps.budget_items:
		frappe.throw(
			_("The project has no Sales Order or Quotation items. Create the Project Budget manually and add Item Group lines.")
		)

	ps.flags.ignore_budget_warnings = True
	ps.flags.ignore_mandatory = True
	ps.insert(ignore_permissions=True)
	return ps.name

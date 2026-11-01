import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import date_diff,nowdate
from frappe.utils import flt

@frappe.whitelist()
def create_project_schedule(project):
    project_doc = frappe.get_doc("Project", project)

    ps = frappe.new_doc("Project Schedule")
    ps.project = project_doc.name
    ps.bill_of_quantity = project_doc.custom_bill_of_quantity
    for row in project_doc.custom_boq_items:
        task = ps.append("project_schedule_tasks")
        task.description = row.item_name
        task.boq_template = row.boq_template_id
        task.item_code = row.item_code


    ps.insert(ignore_permissions=True)
    return ps.name


@frappe.whitelist()
def create_material_request(name):
    project = frappe.get_doc("Project", name)

    if not project.custom_boq_items:
        frappe.throw(_("No BOQ Items found for this project."))

    request = frappe.new_doc("Material Request")
    request.custom_project = name
    request.material_request_type = "Purchase"  

    for item in project.custom_boq_items:
        used_qty = frappe.db.sql("""
            SELECT SUM(qty)
            FROM `tabMaterial Request Item`
            WHERE project = %s AND item_code = %s AND docstatus != 2
        """, (name, item.item_code), as_list=True)

        used_qty_val = flt(used_qty[0][0]) if used_qty and used_qty[0][0] else 0
        available_qty = flt(item.qty) - used_qty_val

        if available_qty > 0:
            request.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "uom": item.uom,
                "qty": available_qty,
                "schedule_date": nowdate(),
                "project": name
            })

    if not request.items:
        frappe.throw(_("No items with available quantity found."))

    request.save(ignore_permissions=True)
    # request.submit()

    return request.name

@frappe.whitelist()
def make_project_budget(project):
    project_doc = frappe.get_doc("Project", project)

    ps = frappe.new_doc("Project Budget")
    ps.project = project_doc.name
    ps.boq_reference = project_doc.custom_bill_of_quantity

    if project_doc.custom_bill_of_quantity:
        boq = frappe.get_doc(
            "Bill of Quantity",
            project_doc.custom_bill_of_quantity
        )

        for row in boq.boq_template:
            budget = ps.append("budget_items")
            budget.category = row.boq_template
            budget.actual_amount = row.total_amount


    ps.insert(ignore_permissions=True)
    return ps.name
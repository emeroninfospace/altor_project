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

    existing = frappe.db.get_value(
        "Project Budget", {"project": project, "docstatus": ["<", 2]}, "name"
    )
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
    ps.boq_reference = project_doc.custom_bill_of_quantity

    # One budget line per Item Group. The BOQ value is kept as a reference;
    # the budgeted (cost) amount is entered by the user.
    if project_doc.custom_bill_of_quantity:
        boq = frappe.get_doc("Bill of Quantity", project_doc.custom_bill_of_quantity)
        lines = {}
        for row in boq.boq_template:
            if not row.boq_template:
                continue
            lines[row.boq_template] = lines.get(row.boq_template, 0) + flt(row.total_amount)
        for item_group, amount in lines.items():
            ps.append("budget_items", {"category": item_group, "boq_amount": amount})

    if not ps.budget_items:
        frappe.throw(
            _("No Item Groups found in the Bill of Quantity. Create the Project Budget manually and add Item Group lines.")
        )

    ps.flags.ignore_budget_warnings = True
    ps.flags.ignore_mandatory = True
    ps.insert(ignore_permissions=True)
    return ps.name

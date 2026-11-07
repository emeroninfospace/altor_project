import json

import frappe


@frappe.whitelist()
def get_my_tasks(filters=None):
	frappe.has_permission("Task", "read", throw=True)
	user = frappe.session.user

	if isinstance(filters, str):
		try:
			filters = json.loads(filters)
		except Exception:
			filters = {}

	filters = filters or {}

	conditions = ""
	values = {}

	if filters.get("project"):
		conditions += " AND t.project = %(project)s"
		values["project"] = filters["project"]

	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return frappe.db.sql(
			f"""
            SELECT
                t.name,
                t.subject,
                t.project,
                t.status,
                t.progress,
                t.description,
                t.parent_task,
                t.is_group,
                t.priority,
                t.exp_start_date,
                t.exp_end_date
            FROM `tabTask` t
            WHERE 1=1
            {conditions}
            ORDER BY t.parent_task, t.idx
        """,
			values,
			as_dict=True,
		)

	values["user"] = user

	return frappe.db.sql(
		f"""
        SELECT DISTINCT
            t.name,
            t.subject,
            t.project,
            t.status,
            t.progress,
            t.description,
            t.parent_task,
            t.is_group,
            t.priority,
            t.exp_start_date,
            t.exp_end_date
        FROM `tabTask` t
        INNER JOIN `tabToDo` td
            ON td.reference_name = t.name
        WHERE
            td.reference_type = 'Task'
            AND td.allocated_to = %(user)s
            AND td.status != 'Cancelled'
            {conditions}
        ORDER BY t.parent_task, t.idx
    """,
		values,
		as_dict=True,
	)


def update_parent_task_progress(doc, method=None):
	if not doc.parent_task:
		return

	parent_task = doc.parent_task

	child_tasks = frappe.get_all(
		"Task", filters={"parent_task": parent_task, "status": ["!=", "Cancelled"]}, fields=["progress"]
	)

	if not child_tasks:
		return

	total_progress = sum(t.progress or 0 for t in child_tasks)
	avg_progress = round(total_progress / len(child_tasks), 2)

	if avg_progress == 0:
		parent_status = "Open"
	elif avg_progress >= 100:
		parent_status = "Completed"
	else:
		parent_status = "Working"

	frappe.db.set_value("Task", parent_task, {"progress": avg_progress, "status": parent_status})

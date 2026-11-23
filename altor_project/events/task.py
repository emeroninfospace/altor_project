import frappe


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

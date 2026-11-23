# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""My Assignments dashboard: the logged-in user's assigned work (Assign To on any document),
its status, and marking it done."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, strip_html, today

LIMIT = 300
# extra columns shown per document type (when the field exists)
DETAIL_FIELDS = {
	"Lead": ("custom_contact_name", "mobile_no", "cost_center"),
	"Task": ("project", "exp_end_date", "progress"),
	"Project": ("percent_complete", "expected_end_date"),
	"Site Visit": ("visit_date", "site_location"),
}


@frappe.whitelist()
def get_my_assignments(filters=None):
	filters = frappe.parse_json(filters) or {}
	user = frappe.session.user
	done = filters.get("show") == "done"
	todo_filters = {"allocated_to": user, "reference_type": ["is", "set"], "reference_name": ["is", "set"]}
	if done:
		todo_filters.update(status="Closed", modified=[">=", add_days(today(), -30)])
	else:
		todo_filters["status"] = "Open"
	todos = frappe.get_all(
		"ToDo",
		filters=todo_filters,
		fields=[
			"name",
			"reference_type",
			"reference_name",
			"description",
			"date",
			"priority",
			"assigned_by",
			"creation",
			"modified",
		],
		order_by="modified desc" if done else "date is null, date asc, creation desc",
		limit_page_length=LIMIT,
	)

	docs = {}
	for doctype in {t.reference_type for t in todos}:
		docs[doctype] = _documents(doctype, [t.reference_name for t in todos if t.reference_type == doctype])
	people = _full_names({t.assigned_by for t in todos if t.assigned_by})

	rows, by_type = [], {}
	now = getdate(today())
	for t in todos:
		info = docs.get(t.reference_type, {}).get(t.reference_name)
		if info is None:
			continue  # the document was deleted or the user cannot read it
		due = t.date or info.get("due")
		overdue = bool(not done and due and getdate(due) < now)
		rows.append(
			{
				"todo": t.name,
				"doctype": t.reference_type,
				"doctype_label": _(t.reference_type),
				"name": t.reference_name,
				"title": info.get("title") or t.reference_name,
				"status": info.get("status"),
				"details": info.get("details") or [],
				"note": (strip_html(t.description or "") or "")[:160],
				"assigned_by": people.get(t.assigned_by) or t.assigned_by,
				"assigned_on": str(t.creation)[:10],
				"due": str(due) if due else None,
				"days_left": date_diff(due, now) if due and not done else None,
				"overdue": overdue,
				"priority": t.priority,
			}
		)
		by_type[t.reference_type] = by_type.get(t.reference_type, 0) + 1

	return {
		"rows": rows,
		"by_type": by_type,
		"status_options": {dt: _status_options(dt) for dt in by_type},
		"summary": {
			"open": cint(frappe.db.count("ToDo", {"allocated_to": user, "status": "Open"})),
			"overdue": sum(1 for r in rows if r["overdue"]),
			"due_today": sum(1 for r in rows if r["due"] and getdate(r["due"]) == now and not done),
			"high": sum(1 for r in rows if r["priority"] == "High"),
			"done_30": cint(
				frappe.db.count(
					"ToDo",
					{"allocated_to": user, "status": "Closed", "modified": [">=", add_days(today(), -30)]},
				)
			),
		},
		"show": "done" if done else "open",
	}


def _documents(doctype, names):
	"""{name: {title, status, due, details}} for the documents the user can read."""
	if not frappe.db.exists("DocType", doctype):
		return {}
	meta = frappe.get_meta(doctype)
	title_field = meta.get_title_field()
	fields = ["name"]
	if title_field and title_field != "name":
		fields.append(title_field)
	if meta.has_field("status"):
		fields.append("status")
	details = [f for f in DETAIL_FIELDS.get(doctype, ()) if meta.has_field(f)]
	fields += [f for f in details if f not in fields]
	try:
		# get_list also returns documents shared with the user (an assignment shares the document)
		found = frappe.get_list(
			doctype, filters={"name": ["in", list(set(names))]}, fields=fields, limit_page_length=0
		)
	except frappe.PermissionError:
		frappe.clear_last_message()
		return {}
	out = {}
	for d in found:
		out[d.name] = {
			"title": d.get(title_field) if title_field else None,
			"status": d.get("status"),
			"due": d.get("exp_end_date") or d.get("expected_end_date"),
			"details": [
				{"label": _(meta.get_label(f)), "value": _format(meta, f, d.get(f))}
				for f in details
				if d.get(f) not in (None, "")
			],
		}
	return out


def _format(meta, fieldname, value):
	df = meta.get_field(fieldname)
	if df and df.fieldtype == "Date":
		return frappe.format(value, {"fieldtype": "Date"})
	if df and df.fieldtype == "Percent":
		return f"{round(float(value or 0))}%"
	return str(value)


def _full_names(users):
	if not users:
		return {}
	return dict(
		frappe.get_all(
			"User", filters={"name": ["in", list(users)]}, fields=["name", "full_name"], as_list=True
		)
	)


def _status_options(doctype):
	"""Statuses the user can pick on the dashboard: a non-submittable document with a Select status
	that the user may edit."""
	meta = frappe.get_meta(doctype)
	df = meta.get_field("status")
	if meta.is_submittable or not df or df.fieldtype != "Select" or df.read_only:
		return []
	if not frappe.has_permission(doctype, "write"):
		return []
	return [o for o in (df.options or "").split("\n") if o and o != "Template"]


@frappe.whitelist()
def set_status(doctype, name, status):
	"""Change the status of an assigned document from the dashboard."""
	if status not in _status_options(doctype):
		frappe.throw(_("{0} cannot be set to {1} here.").format(_(doctype), status))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")
	doc.status = status
	if doctype == "Task" and status == "Completed":
		# ERPNext asks for the completion date of a completed task
		if doc.meta.has_field("completed_on") and not doc.get("completed_on"):
			doc.completed_on = today()
		if doc.meta.has_field("completed_by") and not doc.get("completed_by"):
			doc.completed_by = frappe.session.user
		if doc.meta.has_field("progress"):
			doc.progress = 100
	doc.save()
	return doc.status


@frappe.whitelist()
def mark_done(todo):
	"""Close one of the user's own assignments (the assigner sees it as done)."""
	doc = frappe.get_doc("ToDo", todo)
	if doc.allocated_to != frappe.session.user:
		frappe.throw(_("This assignment is not yours."), frappe.PermissionError)
	doc.status = "Closed"
	doc.save(ignore_permissions=True)
	return True

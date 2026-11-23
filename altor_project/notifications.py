# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Bell notifications for assignments.

* Assign To (any document: Lead, Task, ...): Frappe notifies the assignee on its own. On the live
  site some assignments (e.g. a lead re-assigned back to its creator) got no notification, so a
  check every minute adds the missing one: an open assignment made by someone else, whose
  assignee has no Assignment notification for that document since it was assigned.
* Assign To (assign_to.add / add_multiple, replaced in hooks): the notification is written in the same
  request instead of Frappe's background job, so it shows at once.
* Lead Owner: changing it to another user notifies the new owner.
"""

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import get_title, get_title_html
from frappe.desk.doctype.notification_settings.notification_settings import is_notifications_enabled
from frappe.desk.form.assign_to import notify_assignment as frappe_notify_assignment
from frappe.utils import add_to_date, now_datetime

# assignments younger than this are left to Frappe's own notification (it comes within a second)
GRACE_SECONDS = 30
LOOKBACK_DAYS = 1


def missing_assignment_notifications(now=None):
	"""Open assignments made by someone else whose assignee has no notification for them."""
	now = now or now_datetime()
	return frappe.db.sql(
		"""
		SELECT t.name, t.allocated_to, t.assigned_by, t.reference_type, t.reference_name, t.description
		FROM `tabToDo` t
		WHERE t.status = 'Open'
			AND IFNULL(t.reference_type, '') != '' AND IFNULL(t.reference_name, '') != ''
			AND IFNULL(t.allocated_to, '') != '' AND IFNULL(t.assigned_by, '') != ''
			AND t.assigned_by != t.allocated_to
			AND t.creation BETWEEN %(since)s AND %(until)s
			AND NOT EXISTS (
				SELECT 1 FROM `tabNotification Log` n
				WHERE n.for_user = t.allocated_to AND n.type = 'Assignment'
					AND n.document_type = t.reference_type AND n.document_name = t.reference_name
					AND n.creation >= t.creation - INTERVAL 5 SECOND
			)
		ORDER BY t.creation
		""",
		{
			"since": add_to_date(now, days=-LOOKBACK_DAYS),
			"until": add_to_date(now, seconds=-GRACE_SECONDS),
		},
		as_dict=True,
	)


def notify_missed_assignments():
	"""Scheduler (every minute): add the assignment notifications Frappe did not create."""
	for todo in missing_assignment_notifications():
		try:
			if not _active(todo.allocated_to):
				continue
			notify(
				todo.allocated_to,
				todo.assigned_by,
				todo.reference_type,
				todo.reference_name,
				"{0} assigned a new task {1} {2} to you",
				todo.description,
			)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Assignment notification for ToDo {todo.name}")


def on_lead_update(doc, method=None):
	"""doc_event (Lead on_update): tell the new Lead Owner."""
	owner = doc.get("lead_owner")
	if not owner or owner == frappe.session.user or not doc.has_value_changed("lead_owner"):
		return
	if not _active(owner):
		return
	frappe.db.savepoint("altor_lead_owner_notification")
	try:
		notify(owner, frappe.session.user, "Lead", doc.name, "{0} made you the Lead Owner of {1} {2}")
	except Exception:
		# a notification never stops the lead from saving
		frappe.db.rollback(save_point="altor_lead_owner_notification")
		frappe.log_error(title=f"Lead Owner notification for {doc.name}")


# ---------------------------------------------------------------------------
# Instant assignment notifications
# ---------------------------------------------------------------------------


def notify_assignment_now(assigned_by, allocated_to, doc_type, doc_name, action="CLOSE", description=None):
	"""Frappe's notify_assignment, but a new assignment's notification is written in the same request
	(Frappe hands it to a background job, which on this site sometimes never wrote it)."""
	if action != "ASSIGN":
		return frappe_notify_assignment(assigned_by, allocated_to, doc_type, doc_name, action, description)
	# same rules as Frappe: nothing for a self-assignment or a disabled user
	if not (assigned_by and allocated_to and doc_type and doc_name) or assigned_by == allocated_to:
		return
	if not _active(allocated_to):
		return
	frappe.db.savepoint("altor_assign_notification")
	try:
		notify(
			allocated_to,
			frappe.session.user,
			doc_type,
			doc_name,
			"{0} assigned a new task {1} {2} to you",
			description,
		)
	except Exception:
		# the assignment itself is kept; the minute check (notify_missed_assignments) retries
		frappe.db.rollback(save_point="altor_assign_notification")
		frappe.log_error(title=f"Assignment notification for {doc_type} {doc_name}")


def _with_instant_notification(call):
	from frappe.desk.form import assign_to

	original = assign_to.notify_assignment
	assign_to.notify_assignment = notify_assignment_now
	try:
		return call()
	finally:
		assign_to.notify_assignment = original


@frappe.whitelist()
def add_assignment(args=None):
	"""Replaces frappe.desk.form.assign_to.add (Assign To): same, with the notification written at once."""
	from frappe.desk.form import assign_to

	return _with_instant_notification(lambda: assign_to.add(args))


@frappe.whitelist()
def add_multiple_assignments(args=None):
	"""Replaces frappe.desk.form.assign_to.add_multiple (Assign To from a list)."""
	from frappe.desk.form import assign_to

	return _with_instant_notification(lambda: assign_to.add_multiple(args))


def notify(for_user, from_user, doctype, docname, message, description=None):
	"""One Assignment notification (bell, plus the user's notification email when set up)."""
	language = frappe.db.get_value("User", for_user, "language")
	sender = frappe.db.get_value("User", from_user, "full_name") or from_user
	subject = _(message, lang=language).format(
		frappe.bold(sender),
		frappe.bold(_(doctype, lang=language)),
		get_title_html(get_title(doctype, docname)),
	)
	frappe.get_doc(
		{
			"doctype": "Notification Log",
			"type": "Assignment",
			"for_user": for_user,
			"from_user": from_user,
			"document_type": doctype,
			"document_name": docname,
			"subject": subject,
			"email_content": f"<div>{description}</div>" if description else None,
		}
	).insert(ignore_permissions=True)


def _active(user):
	return bool(frappe.db.get_value("User", user, "enabled")) and is_notifications_enabled(user)

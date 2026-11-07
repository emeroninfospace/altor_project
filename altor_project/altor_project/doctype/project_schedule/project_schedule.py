# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.form import assign_to
from frappe.model.document import Document


class ProjectSchedule(Document):
	@frappe.whitelist()
	def create_tasks(self):
		"""One parent task per work package, one child task per schedule row."""
		if frappe.db.exists("Task", {"custom_project_schedule": self.name}):
			frappe.throw(_("Tasks already created for this Project Schedule"))

		has_item_field = frappe.get_meta("Task").has_field("custom_item_code")
		parent_tasks = {}
		team_users = {}

		for row in self.project_schedule_tasks:
			package = row.work_package or _("General")
			if package not in parent_tasks:
				parent_task = frappe.new_doc("Task")
				parent_task.project = self.project
				parent_task.subject = package
				parent_task.custom_project_schedule = self.name
				parent_task.is_group = 1
				parent_task.insert(ignore_permissions=True)
				parent_tasks[package] = parent_task.name

			child_task = frappe.new_doc("Task")
			child_task.project = self.project
			child_task.subject = row.description or package
			child_task.parent_task = parent_tasks[package]
			child_task.custom_project_schedule = self.name
			child_task.exp_start_date = row.expected_start_date
			child_task.exp_end_date = row.expected_end_date
			child_task.description = row.description
			if has_item_field and row.item_code:
				child_task.custom_item_code = row.item_code
			child_task.insert(ignore_permissions=True)

			if row.project_team:
				if row.project_team not in team_users:
					team = frappe.get_doc("Project Team", row.project_team)
					team_users[row.project_team] = [m.user for m in team.employee_and_user if m.user]
				if team_users[row.project_team]:
					assign_to.add(
						{
							"assign_to": team_users[row.project_team],
							"doctype": "Task",
							"name": child_task.name,
							"description": child_task.subject,
						}
					)

# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.desk.form import assign_to


class ProjectSchedule(Document):
    @frappe.whitelist()
    def create_tasks(self):
        if frappe.db.exists("Task", {
            "custom_project_schedule": self.name
        }):
            frappe.throw("Tasks already created for this Project Schedule")

        parent_tasks = {}
        item_name_cache = {}

        for row in self.project_schedule_tasks:
            if not row.boq_template:
                continue
            if row.boq_template not in parent_tasks:
                parent_task = frappe.new_doc("Task")
                parent_task.project = self.project
                parent_task.subject = row.boq_template
                parent_task.custom_bill_of_quantity = self.bill_of_quantity
                parent_task.custom_project_schedule = self.name
                parent_task.is_group = 1
                parent_task.insert(ignore_permissions=True)

                parent_tasks[row.boq_template] = parent_task.name
            else:
                parent_task = parent_tasks[row.boq_template]

            if self.bill_of_quantity:
                boq = frappe.get_doc("Bill of Quantity", self.bill_of_quantity)

                for boq_item in boq.table_kfog:
                    if not boq_item.item_code:
                        continue

                    if boq_item.item_code not in item_name_cache:
                        item_name_cache[boq_item.item_code] = frappe.db.get_value(
                            "Item",
                            boq_item.item_code,
                            "item_name"
                        )

                    item_name = item_name_cache[boq_item.item_code] or boq_item.item_code

                    child_task = frappe.new_doc("Task")
                    child_task.project = self.project
                    child_task.subject = item_name
                    child_task.parent_task = parent_tasks[row.boq_template]
                    child_task.custom_project_schedule = self.name
                    child_task.custom_item_code = boq_item.item_code
                    child_task.exp_start_date = row.expected_start_date
                    child_task.exp_end_date = row.expected_end_date
                    child_task.description = row.description
                    child_task.insert(ignore_permissions=True)

                    if row.project_team:
                        project_team = frappe.get_doc("Project Team", row.project_team)
                        users = [
                            m.user for m in project_team.employee_and_user if m.user
                        ]

                        if users:
                            assign_to.add({
                                "assign_to": users,
                                "doctype": "Task",
                                "name": child_task.name,
                                "description": child_task.subject
                            })
            else:
                child_task = frappe.new_doc("Task")
                child_task.project = self.project
                child_task.subject = row.description or row.boq_template
                child_task.parent_task = parent_tasks[row.boq_template]
                child_task.custom_project_schedule = self.name
                child_task.exp_start_date = row.expected_start_date
                child_task.exp_end_date = row.expected_end_date
                child_task.description = row.description
                child_task.insert(ignore_permissions=True)

                if row.project_team:
                    project_team = frappe.get_doc("Project Team", row.project_team)
                    users = [
                        m.user for m in project_team.employee_and_user if m.user
                    ]

                    if users:
                        assign_to.add({
                            "assign_to": users,
                            "doctype": "Task",
                            "name": child_task.name,
                            "description": child_task.subject
                        })

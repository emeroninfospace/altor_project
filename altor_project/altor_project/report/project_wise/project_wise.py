# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import frappe
from datetime import datetime


def execute(filters=None):
    filters = filters or {}

    columns = get_columns()
    data = []

    start_date = filters.get("start_date")
    end_date = filters.get("end_date")

    project_filters = {}
    if filters.get("project"):
        project_filters["name"] = filters["project"]

    if start_date and end_date:
        project_filters["expected_start_date"] = ["<=", end_date]
        project_filters["expected_end_date"] = [">=", start_date]
    elif start_date:
        project_filters["expected_end_date"] = [">=", start_date]
    elif end_date:
        project_filters["expected_start_date"] = ["<=", end_date]

    projects = frappe.get_all(
        "Project",
        filters=project_filters,
        fields=[
            "name",
            "project_name",
            "expected_start_date",
            "expected_end_date",
            "percent_complete" 
        ],
        order_by="name"
    )

    user_map = {
        u.name: u.full_name
        for u in frappe.get_all("User", fields=["name", "full_name"])
    }

    # Load all tasks and assignments up front (a few queries in total instead of
    # several per project and per task).
    task_fields = [
        "name", "subject", "status", "priority", "progress",
        "exp_start_date", "exp_end_date", "project", "parent_task",
    ]
    project_names = [p.name for p in projects]
    parent_tasks_by_project, child_tasks_by_parent = {}, {}
    if project_names:
        parent_task_filters = {"project": ["in", project_names], "parent_task": ["is", "not set"]}
        if filters.get("task"):
            parent_task_filters["name"] = filters["task"]
        for t in frappe.get_all("Task", filters=parent_task_filters, fields=task_fields, order_by="name"):
            parent_tasks_by_project.setdefault(t.project, []).append(t)

    parent_names = [t.name for tasks in parent_tasks_by_project.values() for t in tasks]
    if parent_names:
        for t in frappe.get_all(
            "Task", filters={"parent_task": ["in", parent_names]}, fields=task_fields, order_by="name"
        ):
            child_tasks_by_parent.setdefault(t.parent_task, []).append(t)

    all_task_names = parent_names + [t.name for tasks in child_tasks_by_parent.values() for t in tasks]
    assignments = get_assignments(all_task_names)

    for project in projects:
        data.append({
            "name": project.name,
            "project_task": project.project_name,
            "parent": None,
            "indent": 0,
            "expected_start_date": project.expected_start_date,
            "expected_end_date": project.expected_end_date,
            "duration": calculate_duration(project.expected_start_date, project.expected_end_date),
            "progress": project.percent_complete,
        })

        for ptask in parent_tasks_by_project.get(project.name, []):
            data.append(task_row(ptask, project.name, 1, project, assignments, user_map))
            for ctask in child_tasks_by_parent.get(ptask.name, []):
                data.append(task_row(ctask, ptask.name, 2, project, assignments, user_map))

    return columns, data


def get_columns():
    return [
        {
            "label": "Project / Task",
            "fieldname": "project_task",
            "fieldtype": "Data",
            "width": 300
        },
        {
            "label": "Assigned To",
            "fieldname": "assigned_to",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "Expected Start Date",
            "fieldname": "expected_start_date",
            "fieldtype": "Date",
            "width": 150
        },
        {
            "label": "Expected End Date",
            "fieldname": "expected_end_date",
            "fieldtype": "Date",
            "width": 150
        },
        {
            "label": "Duration (Days)",
            "fieldname": "duration",
            "fieldtype": "Int",
            "width": 120
        },
        {
            "label": "Priority",
            "fieldname": "priority",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Status",
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Progress (%)",
            "fieldname": "progress",
            "fieldtype": "Percent",
            "width": 120
        }
    ]


def get_assignments(task_names):
    """Open ToDo assignments for many tasks at once: {task: [user, ...]}."""
    assignments = {}
    if not task_names:
        return assignments
    for todo in frappe.get_all(
        "ToDo",
        filters={"reference_type": "Task", "reference_name": ["in", task_names], "status": "Open"},
        fields=["reference_name", "allocated_to"],
        order_by="creation asc",
    ):
        assignments.setdefault(todo.reference_name, []).append(todo.allocated_to)
    return assignments


def task_row(task, parent, indent, project, assignments, user_map):
    users = assignments.get(task.name, [])
    return {
        "name": task.name,
        "project_task": task.subject,
        "parent": parent,
        "indent": indent,
        "status": task.status,
        "priority": task.priority,
        "expected_start_date": task.exp_start_date or project.expected_start_date,
        "expected_end_date": task.exp_end_date or project.expected_end_date,
        "duration": calculate_duration(task.exp_start_date, task.exp_end_date),
        "progress": task.progress,
        "assigned_to": ", ".join(user_map.get(u, u) for u in users),
        "assigned_to_ids": ", ".join(users),
    }


def calculate_duration(start_date, end_date):
    if not start_date or not end_date:
        return 0
    
    try:
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
        
        delta = end_date - start_date
        return delta.days + 1 
    except Exception:
        return 0
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

    for project in projects:
        project_duration = calculate_duration(
            project.expected_start_date, 
            project.expected_end_date
        )
        
        data.append({
            "name": project.name,
            "project_task": project.project_name,
            "parent": None,
            "indent": 0,
            "expected_start_date": project.expected_start_date,
            "expected_end_date": project.expected_end_date,
            "duration": project_duration, 
            "progress": project.percent_complete,
        })

        parent_task_filters = {
            "project": project.name,
            "parent_task": ["is", "not set"]
        }

        if filters.get("task"):
            parent_task_filters["name"] = filters["task"]

        parent_tasks = frappe.get_all(
            "Task",
            filters=parent_task_filters,
            fields=[
                "name",
                "subject",
                "status",
                "priority",
                "progress",
                "exp_start_date",  
                "exp_end_date"     
            ],
            order_by="name"
        )

        for ptask in parent_tasks:
            assigned_users = get_assigned_users(ptask.name, user_map)
            
            task_duration = calculate_duration(ptask.exp_start_date, ptask.exp_end_date)

            data.append({
                "name": ptask.name,
                "project_task": ptask.subject,
                "parent": project.name,
                "indent": 1,
                "status": ptask.status,
                "priority": ptask.priority,
                "expected_start_date": ptask.exp_start_date or project.expected_start_date,
                "expected_end_date": ptask.exp_end_date or project.expected_end_date,
                "duration": task_duration,  
                "progress": ptask.progress,
                "assigned_to": assigned_users["names"],
                "assigned_to_ids": assigned_users["ids"]
            })

            child_tasks = frappe.get_all(
                "Task",
                filters={"parent_task": ptask.name},
                fields=[
                    "name",
                    "subject",
                    "status",
                    "priority",
                    "progress",
                    "exp_start_date",  
                    "exp_end_date"     
                ],
                order_by="name"
            )

            for ctask in child_tasks:
                assigned_users = get_assigned_users(ctask.name, user_map)
                
                child_task_duration = calculate_duration(ctask.exp_start_date, ctask.exp_end_date)

                data.append({
                    "name": ctask.name,
                    "project_task": ctask.subject,
                    "parent": ptask.name,
                    "indent": 2,
                    "status": ctask.status,
                    "priority": ctask.priority,
                    "expected_start_date": ctask.exp_start_date or project.expected_start_date,
                    "expected_end_date": ctask.exp_end_date or project.expected_end_date,
                    "duration": child_task_duration,  
                    "progress": ctask.progress,
                    "assigned_to": assigned_users["names"],
                    "assigned_to_ids": assigned_users["ids"]
                })

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


def get_assigned_users(task_name, user_map):
    users = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": "Task",
            "reference_name": task_name,
            "status": "Open"
        },
        pluck="allocated_to"
    )

    full_names = []
    user_ids = []

    for u in users:
        full_names.append(user_map.get(u, u))
        user_ids.append(u)

    return {
        "names": ", ".join(full_names),
        "ids": ", ".join(user_ids)
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
# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff, nowdate


def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	summary = get_report_summary(data)

	return columns, data, None, chart, summary


def get_columns():
	return [
		{"label": "Project Name", "fieldname": "project_name", "fieldtype": "Data", "width": 200},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 120},
		{
			"label": "Expected Start Date",
			"fieldname": "expected_start_date",
			"fieldtype": "Date",
			"width": 120,
		},
		{"label": "Expected End Date", "fieldname": "expected_end_date", "fieldtype": "Date", "width": 120},
		{"label": "Duration (Days)", "fieldname": "duration", "fieldtype": "Int", "width": 120},
		{"label": "Actual Hours", "fieldname": "actual_hours", "fieldtype": "Float", "width": 120},
		{
			"label": "Total Billable Amount",
			"fieldname": "billable_amount",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": "Total Costing Amount",
			"fieldname": "costing_amount",
			"fieldtype": "Currency",
			"width": 150,
		},
	]


def get_data(filters=None):
	filters = filters or {}

	conditions = []
	values = []

	if filters.get("project"):
		conditions.append("p.name = %s")
		values.append(filters.get("project"))

	if filters.get("from_date"):
		conditions.append("p.expected_end_date >= %s")
		values.append(filters.get("from_date"))

	if filters.get("to_date"):
		conditions.append("p.expected_start_date <= %s")
		values.append(filters.get("to_date"))

	where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

	projects = frappe.db.sql(
		f"""
        SELECT
            p.name,
            p.project_name,
            p.status,
            p.expected_start_date,
            p.expected_end_date
        FROM `tabProject` p
        {where_clause}
    """,
		values,
		as_dict=True,
	)

	data = []
	today = nowdate()
	names = [p.name for p in projects]

	# One grouped query each for timesheets and tasks instead of two queries per project
	timesheets, tasks = {}, {}
	if names:
		ts_conditions = ["tsd.project IN %(projects)s", "ts.docstatus = 1"]
		ts_values = {"projects": tuple(names)}
		if filters.get("from_date"):
			ts_conditions.append("ts.start_date >= %(from_date)s")
			ts_values["from_date"] = filters.get("from_date")
		if filters.get("to_date"):
			ts_conditions.append("ts.end_date <= %(to_date)s")
			ts_values["to_date"] = filters.get("to_date")

		for row in frappe.db.sql(
			f"""
            SELECT
                tsd.project,
                COALESCE(SUM(tsd.hours), 0) AS total_hours,
                COALESCE(SUM(tsd.billing_amount), 0) AS total_billable,
                COALESCE(SUM(tsd.costing_amount), 0) AS total_costing
            FROM `tabTimesheet Detail` tsd
            INNER JOIN `tabTimesheet` ts ON ts.name = tsd.parent
            WHERE {" AND ".join(ts_conditions)}
            GROUP BY tsd.project
        """,
			ts_values,
			as_dict=True,
		):
			timesheets[row.project] = row

		for row in frappe.db.sql(
			"""
            SELECT
                project,
                COUNT(*) AS total_tasks,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) AS completed_tasks,
                SUM(CASE WHEN exp_end_date < %(today)s AND status != 'Completed' THEN 1 ELSE 0 END) AS overdue_tasks
            FROM `tabTask`
            WHERE project IN %(projects)s
            GROUP BY project
        """,
			{"today": today, "projects": tuple(names)},
			as_dict=True,
		):
			tasks[row.project] = row

	empty_ts = frappe._dict(total_hours=0, total_billable=0, total_costing=0)
	empty_tasks = frappe._dict(total_tasks=0, completed_tasks=0, overdue_tasks=0)

	for project in projects:
		timesheet_data = timesheets.get(project.name, empty_ts)
		task_data = tasks.get(project.name, empty_tasks)
		total_tasks = int(task_data.total_tasks or 0)
		completed_tasks = int(task_data.completed_tasks or 0)

		percent_complete = 0
		if total_tasks > 0:
			percent_complete = round((completed_tasks / total_tasks) * 100, 1)

		duration = None
		if project.expected_start_date and project.expected_end_date:
			duration = date_diff(project.expected_end_date, project.expected_start_date)

		data.append(
			{
				"project_name": project.project_name,
				"status": project.status,
				"expected_start_date": project.expected_start_date,
				"expected_end_date": project.expected_end_date,
				"duration": duration,
				"actual_hours": timesheet_data.total_hours,
				"billable_amount": timesheet_data.total_billable,
				"costing_amount": timesheet_data.total_costing,
				"percent_complete": percent_complete,
				"total_tasks": total_tasks,
				"completed_tasks": completed_tasks,
				"overdue_tasks": int(task_data.overdue_tasks or 0),
			}
		)

	return data


def get_chart(data):
	if not data:
		return None

	sorted_data = sorted(data, key=lambda x: x.get("actual_hours", 0), reverse=True)[:20]

	labels = [row["project_name"] for row in sorted_data]

	datasets = [
		{"name": "Actual Hours", "values": [row["actual_hours"] for row in sorted_data], "chart_type": "bar"},
		{
			"name": "Billable Amount",
			"values": [row["billable_amount"] for row in sorted_data],
			"chart_type": "bar",
		},
		{
			"name": "Costing Amount",
			"values": [row["costing_amount"] for row in sorted_data],
			"chart_type": "bar",
		},
	]

	return {
		"data": {"labels": labels, "datasets": datasets},
		"type": "bar",
		"height": 300,
	}


def get_report_summary(data):
	if not data:
		return None

	total_projects = len(data)
	if total_projects == 0:
		return None

	avg_completion = sum(row.get("percent_complete", 0) for row in data) / total_projects
	total_tasks = sum(row.get("total_tasks", 0) for row in data)
	completed_tasks = sum(row.get("completed_tasks", 0) for row in data)
	overdue_tasks = sum(row.get("overdue_tasks", 0) for row in data)

	return [
		{
			"value": round(avg_completion, 1),
			"indicator": "Green" if avg_completion >= 70 else "Orange" if avg_completion >= 40 else "Red",
			"label": "Average Completion %",
			"datatype": "Percent",
		},
		{
			"value": total_tasks,
			"indicator": "Blue",
			"label": "Total Tasks",
			"datatype": "Int",
		},
		{
			"value": completed_tasks,
			"indicator": "Green",
			"label": "Completed Tasks",
			"datatype": "Int",
		},
		{
			"value": overdue_tasks,
			"indicator": "Green" if overdue_tasks == 0 else "Red",
			"label": "Overdue Tasks",
			"datatype": "Int",
		},
	]

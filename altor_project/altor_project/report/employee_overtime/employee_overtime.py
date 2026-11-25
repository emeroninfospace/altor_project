# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Hours and overtime per employee from submitted Timesheets (the client's monthly OT sheet).

OT hours (weighted) = OT 1 x OT 1 Multiplier + OT 2 x OT 2 Multiplier. OT rate per hour =
OT amount / weighted OT hours (own staff: Basic / days in the month / hours per day; outsourced:
the hourly rate).
"""

import frappe
from frappe import _
from frappe.utils import flt

from altor_project.labour import get_settings


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.from_date or not filters.to_date:
		frappe.throw(_("Select From Date and To Date."))
	if not frappe.db.has_column("Timesheet Detail", "custom_labour_cost"):
		return get_columns(filters), []
	data = get_data(filters)
	return get_columns(filters), data, None, None, get_summary(data)


def get_data(filters):
	s = get_settings()
	if frappe.db.has_column("Timesheet Detail", "custom_employee"):
		# crew Timesheets: each row has its own employee, worker type and agency
		emp = "COALESCE(NULLIF(td.custom_employee, ''), ts.employee)"
		wtype = "COALESCE(NULLIF(td.custom_worker_type, ''), NULLIF(ts.custom_worker_type, ''), 'Own Staff')"
		supplier = "COALESCE(NULLIF(td.custom_manpower_supplier, ''), ts.custom_manpower_supplier)"
	else:
		emp, supplier = "ts.employee", "ts.custom_manpower_supplier"
		wtype = "IFNULL(ts.custom_worker_type, 'Own Staff')"
	conditions = ["ts.docstatus = 1", "DATE(td.from_time) BETWEEN %(from_date)s AND %(to_date)s"]
	for field, column in (
		("company", "ts.company"),
		("employee", emp),
		("project", "td.project"),
		("worker_type", wtype),
		("supplier", supplier),
	):
		if filters.get(field):
			conditions.append(f"{column} = %({field})s")
	by_project = filters.get("group_by") == "Employee and Project"
	where = " AND ".join(conditions)
	project_col = "project" if by_project else "''"
	# row values first, then grouped by plain columns (MariaDB's ONLY_FULL_GROUP_BY)
	rows = frappe.db.sql(
		f"""
		SELECT employee, MAX(employee_name) AS employee_name, MAX(worker_type) AS worker_type,
			MAX(supplier) AS supplier, {project_col} AS project, COUNT(DISTINCT day) AS days,
			SUM(normal_hours) AS normal_hours, SUM(ot1_hours) AS ot1_hours, SUM(ot2_hours) AS ot2_hours,
			SUM(ot_amount) AS ot_amount, SUM(total_cost) AS total_cost
		FROM (
			SELECT {emp} AS employee, IFNULL(e.employee_name, ts.employee_name) AS employee_name,
				{wtype} AS worker_type, {supplier} AS supplier, td.project, DATE(td.from_time) AS day,
				td.custom_normal_hours AS normal_hours, td.custom_ot1_hours AS ot1_hours,
				td.custom_ot2_hours AS ot2_hours, td.custom_ot_cost AS ot_amount, td.custom_labour_cost AS total_cost
			FROM `tabTimesheet Detail` td
			INNER JOIN `tabTimesheet` ts ON ts.name = td.parent
			LEFT JOIN `tabEmployee` e ON e.name = {emp}
			WHERE {where}
		) ot_rows
		GROUP BY employee, {project_col}
		ORDER BY MAX(employee_name), {project_col}
		""",
		filters,
		as_dict=True,
	)
	for row in rows:
		row.ot_hours_weighted = flt(row.ot1_hours) * s.ot_multiplier + flt(row.ot2_hours) * s.ot2_multiplier
		row.ot_rate = flt(row.ot_amount) / row.ot_hours_weighted if row.ot_hours_weighted else 0
		row.normal_cost = flt(row.total_cost) - flt(row.ot_amount)
	return rows


def get_columns(filters):
	columns = [
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 130,
		},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
		{"label": _("Worker Type"), "fieldname": "worker_type", "fieldtype": "Data", "width": 100},
		{
			"label": _("Manpower Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 140,
		},
	]
	if filters.get("group_by") == "Employee and Project":
		columns.append(
			{
				"label": _("Project"),
				"fieldname": "project",
				"fieldtype": "Link",
				"options": "Project",
				"width": 140,
			}
		)
	columns += [
		{"label": _("Days Worked"), "fieldname": "days", "fieldtype": "Int", "width": 90},
		{"label": _("Normal Hours"), "fieldname": "normal_hours", "fieldtype": "Float", "width": 100},
		{"label": _("OT 1 Hours"), "fieldname": "ot1_hours", "fieldtype": "Float", "width": 90},
		{"label": _("OT 2 Hours"), "fieldname": "ot2_hours", "fieldtype": "Float", "width": 90},
		{
			"label": _("OT Hours (Weighted)"),
			"fieldname": "ot_hours_weighted",
			"fieldtype": "Float",
			"width": 130,
		},
		{"label": _("OT Rate / Hour"), "fieldname": "ot_rate", "fieldtype": "Currency", "width": 110},
		{"label": _("OT Amount"), "fieldname": "ot_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Normal Hours Cost"), "fieldname": "normal_cost", "fieldtype": "Currency", "width": 130},
		{"label": _("Total Labour Cost"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 130},
	]
	return columns


def get_summary(data):
	own = sum(flt(r.total_cost) for r in data if r.worker_type != "Outsourced")
	out = sum(flt(r.total_cost) for r in data if r.worker_type == "Outsourced")
	return [
		{"label": _("Own Staff Cost"), "value": own, "datatype": "Currency", "indicator": "Blue"},
		{"label": _("Outsourced Cost"), "value": out, "datatype": "Currency", "indicator": "Orange"},
		{
			"label": _("Overtime Amount"),
			"value": sum(flt(r.ot_amount) for r in data),
			"datatype": "Currency",
			"indicator": "Red",
		},
		{
			"label": _("OT Hours (Weighted)"),
			"value": sum(flt(r.ot_hours_weighted) for r in data),
			"datatype": "Float",
		},
	]

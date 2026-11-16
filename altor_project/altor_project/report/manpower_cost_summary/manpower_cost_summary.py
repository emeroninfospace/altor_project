# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Labour cost from submitted Timesheets, grouped for review and for checking agency invoices."""

import frappe
from frappe import _
from frappe.utils import flt

from altor_project.labour import labour_sql

GROUP_BY = {
	"Project": ("l.project", "Link", "Project"),
	"Manpower Supplier": ("IFNULL(l.supplier, '')", "Link", "Supplier"),
	"Employee": ("IFNULL(l.employee, '')", "Link", "Employee"),
	"Designation": ("IFNULL(l.designation, '')", "Link", "Designation"),
	"Date": ("l.posting_date", "Date", None),
	"Item Group": ("IFNULL(l.item_group, '')", "Link", "Item Group"),
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group_by = filters.group_by if filters.group_by in GROUP_BY else "Project"
	key_sql, fieldtype, options = GROUP_BY[group_by]

	conditions = ["l.posting_date BETWEEN %(from_date)s AND %(to_date)s"]
	for field, column in (
		("company", "l.company"),
		("project", "l.project"),
		("worker_type", "l.worker_type"),
		("supplier", "l.supplier"),
	):
		if filters.get(field):
			conditions.append(f"{column} = %({field})s")

	data = frappe.db.sql(
		f"""
		SELECT {key_sql} AS group_key,
			MAX(l.employee_name) AS employee_name,
			COUNT(DISTINCT l.voucher) AS entries,
			COUNT(DISTINCT l.posting_date) AS days,
			SUM(l.no_of_workers) AS man_days,
			SUM(l.hours) AS hours,
			SUM(l.ot_hours) AS ot_hours,
			SUM(l.ot2_hours) AS ot2_hours,
			SUM(CASE WHEN l.worker_type = 'Outsourced' THEN 0 ELSE l.amount END) AS own_cost,
			SUM(CASE WHEN l.worker_type = 'Outsourced' THEN l.amount ELSE 0 END) AS outsourced_cost,
			SUM(l.amount) AS total_cost
		FROM ({labour_sql()}) l
		WHERE {" AND ".join(conditions)}
		GROUP BY group_key
		ORDER BY total_cost DESC
		""",
		filters,
		as_dict=True,
	)
	for row in data:
		all_hours = flt(row.hours) + flt(row.ot_hours) + flt(row.ot2_hours)
		row.avg_hourly_cost = flt(row.total_cost) / all_hours if all_hours else 0
		if not row.group_key:
			row.group_key = _("Not Set")

	columns = [
		{
			"fieldname": "group_key",
			"label": _(group_by),
			"fieldtype": fieldtype,
			"options": options,
			"width": 180,
		},
	]
	if group_by == "Employee":
		columns.append(
			{"fieldname": "employee_name", "label": _("Employee Name"), "fieldtype": "Data", "width": 160}
		)
	columns += [
		{"fieldname": "entries", "label": _("Timesheets"), "fieldtype": "Int", "width": 90},
		{"fieldname": "days", "label": _("Days"), "fieldtype": "Int", "width": 70},
		{"fieldname": "man_days", "label": _("Man-Days"), "fieldtype": "Int", "width": 90},
		{"fieldname": "hours", "label": _("Normal Hours"), "fieldtype": "Float", "width": 100},
		{"fieldname": "ot_hours", "label": _("OT 1 Hours"), "fieldtype": "Float", "width": 90},
		{"fieldname": "ot2_hours", "label": _("OT 2 Hours"), "fieldtype": "Float", "width": 90},
		{"fieldname": "own_cost", "label": _("Own Staff Cost"), "fieldtype": "Currency", "width": 130},
		{
			"fieldname": "outsourced_cost",
			"label": _("Outsourced Cost"),
			"fieldtype": "Currency",
			"width": 130,
		},
		{"fieldname": "total_cost", "label": _("Total Cost"), "fieldtype": "Currency", "width": 130},
		{
			"fieldname": "avg_hourly_cost",
			"label": _("Avg Cost / Hour"),
			"fieldtype": "Currency",
			"width": 120,
		},
	]

	chart = None
	if data:
		top = data[:15]
		chart = {
			"data": {
				"labels": [str(r.group_key) for r in top],
				"datasets": [
					{"name": _("Own Staff"), "values": [flt(r.own_cost) for r in top]},
					{"name": _("Outsourced"), "values": [flt(r.outsourced_cost) for r in top]},
				],
			},
			"type": "bar",
			"barOptions": {"stacked": 1},
			"colors": ["#2490ef", "#f08c00"],
			"fieldtype": "Currency",
		}

	total_own = sum(flt(r.own_cost) for r in data)
	total_out = sum(flt(r.outsourced_cost) for r in data)
	summary = [
		{"value": total_own, "label": _("Own Staff Cost"), "datatype": "Currency", "indicator": "Blue"},
		{"value": total_out, "label": _("Outsourced Cost"), "datatype": "Currency", "indicator": "Orange"},
		{
			"value": total_own + total_out,
			"label": _("Total Manpower Cost"),
			"datatype": "Currency",
			"indicator": "Green",
		},
		{"value": sum(flt(r.man_days) for r in data), "label": _("Man-Days"), "datatype": "Int"},
	]
	return columns, data, None, chart, summary

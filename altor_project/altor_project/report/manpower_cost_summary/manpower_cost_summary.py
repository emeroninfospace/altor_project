# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Labour cost from submitted Manpower Entries, grouped for review and for checking agency invoices."""

import frappe
from frappe import _
from frappe.utils import flt

GROUP_BY = {
	"Project": ("me.project", "Link", "Project"),
	"Manpower Supplier": ("IFNULL(d.supplier, '')", "Link", "Supplier"),
	"Employee": ("IFNULL(d.employee, '')", "Link", "Employee"),
	"Designation": ("IFNULL(d.designation, '')", "Link", "Designation"),
	"Date": ("me.posting_date", "Date", None),
	"Item Group": ("COALESCE(NULLIF(d.item_group, ''), me.item_group)", "Link", "Item Group"),
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	group_by = filters.group_by if filters.group_by in GROUP_BY else "Project"
	key_sql, fieldtype, options = GROUP_BY[group_by]

	conditions = ["me.docstatus = 1", "me.posting_date BETWEEN %(from_date)s AND %(to_date)s"]
	for field, column in (
		("company", "me.company"),
		("project", "me.project"),
		("worker_type", "d.worker_type"),
		("supplier", "d.supplier"),
	):
		if filters.get(field):
			conditions.append(f"{column} = %({field})s")

	data = frappe.db.sql(
		f"""
		SELECT {key_sql} AS group_key,
			MAX(d.employee_name) AS employee_name,
			COUNT(DISTINCT me.name) AS entries,
			COUNT(DISTINCT me.posting_date) AS days,
			SUM(d.no_of_workers) AS man_days,
			SUM(d.no_of_workers * IFNULL(d.working_hours, 0)) AS hours,
			SUM(d.no_of_workers * IFNULL(d.ot_hours, 0)) AS ot_hours,
			SUM(CASE WHEN d.worker_type = 'Outsourced' THEN 0 ELSE d.amount END) AS own_cost,
			SUM(CASE WHEN d.worker_type = 'Outsourced' THEN d.amount ELSE 0 END) AS outsourced_cost,
			SUM(d.amount) AS total_cost
		FROM `tabManpower Entry Detail` d
		INNER JOIN `tabManpower Entry` me ON me.name = d.parent
		WHERE {" AND ".join(conditions)}
		GROUP BY group_key
		ORDER BY total_cost DESC
		""",
		filters,
		as_dict=True,
	)
	for row in data:
		row.avg_hourly_cost = (
			flt(row.total_cost) / flt(row.hours + row.ot_hours) if flt(row.hours + row.ot_hours) else 0
		)
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
		{"fieldname": "entries", "label": _("Entries"), "fieldtype": "Int", "width": 80},
		{"fieldname": "days", "label": _("Days"), "fieldtype": "Int", "width": 70},
		{"fieldname": "man_days", "label": _("Man-Days"), "fieldtype": "Int", "width": 90},
		{"fieldname": "hours", "label": _("Hours"), "fieldtype": "Float", "width": 90},
		{"fieldname": "ot_hours", "label": _("OT Hours"), "fieldtype": "Float", "width": 90},
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

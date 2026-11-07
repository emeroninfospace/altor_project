# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from altor_project.budget import update_submitted_budget


def execute(filters=None):
	filters = frappe._dict(filters or {})

	budget_filters = {"docstatus": 1}
	if filters.project:
		budget_filters["project"] = filters.project
	if filters.company:
		budget_filters["company"] = filters.company

	budgets = frappe.get_list(
		"Project Budget",
		filters=budget_filters,
		fields=["name", "project", "warning_threshold"],
		order_by="project asc",
		limit_page_length=0,
	)

	if filters.recalculate:
		for b in budgets:
			update_submitted_budget(b.name)

	data = []
	if budgets:
		line_filters = {"parenttype": "Project Budget", "parent": ["in", [b.name for b in budgets]]}
		if filters.item_group:
			line_filters["category"] = filters.item_group
		if filters.budget_status:
			line_filters["budget_status"] = filters.budget_status
		project_of = {b.name: b.project for b in budgets}
		for line in frappe.get_all(
			"Project Budget Item",
			filters=line_filters,
			fields=[
				"parent",
				"category",
				"quoted_amount",
				"budgeted_amount",
				"committed_amount",
				"actual_amount",
				"utilized_amount",
				"variance",
				"utilization_percentage",
				"budget_status",
			],
			order_by="parent asc, idx asc",
		):
			line.project = project_of.get(line.parent)
			line.project_budget = line.parent
			data.append(line)

	return get_columns(), data, None, get_chart(data)


def get_columns():
	currency = {"fieldtype": "Currency", "width": 130}
	return [
		{
			"fieldname": "project",
			"label": _("Project"),
			"fieldtype": "Link",
			"options": "Project",
			"width": 150,
		},
		{
			"fieldname": "category",
			"label": _("Item Group"),
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 160,
		},
		{"fieldname": "quoted_amount", "label": _("Quoted Amount"), **currency},
		{"fieldname": "budgeted_amount", "label": _("Budget"), **currency},
		{"fieldname": "committed_amount", "label": _("Committed"), **currency},
		{"fieldname": "actual_amount", "label": _("Actual"), **currency},
		{"fieldname": "utilized_amount", "label": _("Utilized"), **currency},
		{"fieldname": "variance", "label": _("Balance"), **currency},
		{
			"fieldname": "utilization_percentage",
			"label": _("Utilization %"),
			"fieldtype": "Percent",
			"width": 110,
		},
		{"fieldname": "budget_status", "label": _("Status"), "fieldtype": "Data", "width": 120},
		{
			"fieldname": "project_budget",
			"label": _("Project Budget"),
			"fieldtype": "Link",
			"options": "Project Budget",
			"width": 150,
		},
	]


def get_chart(data):
	if not data:
		return None
	by_group = {}
	for row in data:
		g = by_group.setdefault(row.category, [0, 0])
		g[0] += flt(row.budgeted_amount)
		g[1] += flt(row.utilized_amount)
	labels = list(by_group)[:20]
	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Budget"), "values": [by_group[g][0] for g in labels]},
				{"name": _("Utilized"), "values": [by_group[g][1] for g in labels]},
			],
		},
		"type": "bar",
		"colors": ["#2490ef", "#f08c00"],
		"fieldtype": "Currency",
	}

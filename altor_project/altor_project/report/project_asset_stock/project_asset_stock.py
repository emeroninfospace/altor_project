# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Project Asset Stock: every asset item with all its purchases added up.

4 bought at 300 and 5 at 250 show as one line: 9 purchased, average unit cost 272.22.
Averages are weighted by the quantity still owned (purchased less damaged / lost).
"""

import frappe
from frappe import _
from frappe.utils import flt

from altor_project.assets import item_stock


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return columns(), data(filters)


def columns():
	cur = "Company:company:default_currency"
	return [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
		{"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 200},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 130,
		},
		{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 70},
		{"label": _("Purchases"), "fieldname": "purchases", "fieldtype": "Int", "width": 90},
		{"label": _("Purchased"), "fieldname": "qty", "fieldtype": "Float", "width": 100},
		{"label": _("On Projects"), "fieldname": "on_projects", "fieldtype": "Float", "width": 100},
		{"label": _("Damaged / Lost"), "fieldname": "damaged", "fieldtype": "Float", "width": 110},
		{"label": _("Available"), "fieldname": "available", "fieldtype": "Float", "width": 100},
		{
			"label": _("Average Unit Cost"),
			"fieldname": "avg_unit_cost",
			"fieldtype": "Currency",
			"options": cur,
			"width": 130,
		},
		{
			"label": _("Available Value"),
			"fieldname": "available_value",
			"fieldtype": "Currency",
			"options": cur,
			"width": 130,
		},
		{
			"label": _("Avg. Rate / Unit / Day"),
			"fieldname": "avg_daily_rate",
			"fieldtype": "Currency",
			"options": cur,
			"precision": 4,
			"width": 140,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"hidden": 1,
		},
	]


def data(filters):
	conditions = {"disabled": 0, "item_code": ["is", "set"]}
	for field in ("company", "item_code", "item_group"):
		if filters.get(field):
			conditions[field] = filters.get(field)
	pairs = frappe.get_all(
		"Project Asset",
		filters=conditions,
		fields=["item_code", "company"],
		group_by="item_code, company",
		order_by="item_code",
	)
	rows = []
	for pair in pairs:
		s = item_stock(pair.item_code, pair.company)
		if not s.purchases or (filters.get("only_available") and s.available <= 0):
			continue
		rows.append(
			{
				"item_code": s.item_code,
				"asset_name": s.asset_name,
				"item_group": s.item_group,
				"uom": s.uom,
				"purchases": s.purchases,
				"qty": s.qty,
				"on_projects": s.on_projects,
				"damaged": s.damaged,
				"available": s.available,
				"avg_unit_cost": s.avg_unit_cost,
				"available_value": flt(s.available * s.avg_unit_cost, 2),
				"avg_daily_rate": s.avg_daily_rate,
				"company": pair.company,
			}
		)
	if rows:
		rows.append(total_row(rows))
	return rows


def total_row(rows):
	"""Quantities and value added up; the averages are left out (a sum of averages means nothing)."""
	row = {"item_code": _("Total"), "is_total_row": 1}
	for field in ("purchases", "qty", "on_projects", "damaged", "available", "available_value"):
		row[field] = sum(flt(r.get(field)) for r in rows)
	return row

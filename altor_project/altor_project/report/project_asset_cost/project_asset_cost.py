# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Cost of Project Assets charged to projects in a period.

Depreciation = qty x rate per unit per day x days on the project within the period (delivery date to
return date, or to the period end while still on site). Damage cost is counted in the period of the
return. Same calculation as the Project Budget (altor_project.assets).
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from altor_project.assets import charge_days


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.from_date or not filters.to_date:
		frappe.throw(_("Select From Date and To Date."))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_columns():
	return [
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 150,
		},
		{
			"label": _("Allocation"),
			"fieldname": "allocation",
			"fieldtype": "Link",
			"options": "Asset Allocation",
			"width": 140,
		},
		{
			"label": _("Project Asset"),
			"fieldname": "project_asset",
			"fieldtype": "Link",
			"options": "Project Asset",
			"width": 140,
		},
		{"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 220},
		{
			"label": _("Item Group"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 140,
		},
		{"label": _("Delivered On"), "fieldname": "delivery_date", "fieldtype": "Date", "width": 100},
		{"label": _("Issued"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{"label": _("Returned"), "fieldname": "returned_qty", "fieldtype": "Float", "width": 85},
		{"label": _("Damaged / Lost"), "fieldname": "damaged_qty", "fieldtype": "Float", "width": 100},
		{"label": _("On Site at Period End"), "fieldname": "on_site_qty", "fieldtype": "Float", "width": 120},
		{"label": _("Rate / Unit / Day"), "fieldname": "daily_rate", "fieldtype": "Currency", "width": 110},
		{"label": _("Unit Days"), "fieldname": "unit_days", "fieldtype": "Float", "width": 90},
		{"label": _("Depreciation"), "fieldname": "depreciation", "fieldtype": "Currency", "width": 120},
		{"label": _("Damage Cost"), "fieldname": "damage_cost", "fieldtype": "Currency", "width": 110},
		{"label": _("Total Cost"), "fieldname": "total_cost", "fieldtype": "Currency", "width": 120},
	]


def get_data(filters):
	conditions = ["a.docstatus = 1", "a.delivery_date <= %(to_date)s"]
	for field, column in (
		("company", "a.company"),
		("project", "a.project"),
		("cost_center", "a.cost_center"),
		("project_asset", "i.project_asset"),
		("item_group", "i.item_group"),
	):
		if filters.get(field):
			conditions.append(f"{column} = %({field})s")
	rows = frappe.db.sql(
		f"""
		SELECT a.name AS allocation, a.project, a.delivery_date, i.name AS row_name, i.project_asset,
			i.asset_name, i.item_group, i.qty, i.daily_rate, i.charge_until
		FROM `tabAsset Allocation Item` i
		INNER JOIN `tabAsset Allocation` a ON a.name = i.parent
		WHERE {" AND ".join(conditions)}
		ORDER BY a.project, a.delivery_date, i.idx
		""",
		filters,
		as_dict=True,
	)
	if not rows:
		return []

	returns = {}
	for r in frappe.db.sql(
		"""
		SELECT ri.allocation_item, ar.return_date, ri.returned_qty, ri.damaged_qty, ri.damage_cost
		FROM `tabAsset Return Item` ri
		INNER JOIN `tabAsset Return` ar ON ar.name = ri.parent
		WHERE ar.docstatus = 1 AND ri.allocation_item IN %s
		""",
		(tuple(r.row_name for r in rows),),
		as_dict=True,
	):
		returns.setdefault(r.allocation_item, []).append(r)

	data = []
	for row in rows:
		figures = row_cost(row, returns.get(row.row_name, []), filters.from_date, filters.to_date)
		if not (figures.depreciation or figures.damage_cost or figures.on_site_qty):
			continue
		row.update(figures)
		data.append(row)
	return data


def row_cost(row, returns, from_date, to_date):
	"""Cost of one allocation row within [from_date, to_date]."""
	to_date = getdate(to_date)
	rate = flt(row.daily_rate)
	unit_days = damage = returned = damaged = 0.0
	back_by_end = 0.0
	for r in returns:
		qty_back = flt(r.returned_qty) + flt(r.damaged_qty)
		end = min(getdate(r.return_date), to_date)
		unit_days += qty_back * charge_days(row.delivery_date, end, row.charge_until, from_date)
		if getdate(r.return_date) <= to_date:
			back_by_end += qty_back
			returned += flt(r.returned_qty)
			damaged += flt(r.damaged_qty)
			if getdate(r.return_date) >= getdate(from_date):
				damage += flt(r.damage_cost)
	still_out = flt(row.qty) - sum(flt(r.returned_qty) + flt(r.damaged_qty) for r in returns)
	unit_days += max(still_out, 0) * charge_days(row.delivery_date, to_date, row.charge_until, from_date)
	depreciation = flt(unit_days * rate, 2)
	return frappe._dict(
		returned_qty=returned,
		damaged_qty=damaged,
		on_site_qty=max(flt(row.qty) - back_by_end, 0),
		unit_days=unit_days,
		depreciation=depreciation,
		damage_cost=flt(damage, 2),
		total_cost=flt(depreciation + damage, 2),
	)


def get_chart(data):
	if not data:
		return None
	by_project = {}
	for row in data:
		by_project[row.project] = by_project.get(row.project, 0) + row.total_cost
	top = sorted(by_project.items(), key=lambda x: -x[1])[:12]
	return {
		"data": {
			"labels": [p for p, _v in top],
			"datasets": [{"name": _("Asset Cost"), "values": [flt(v, 2) for _p, v in top]}],
		},
		"type": "bar",
		"fieldtype": "Currency",
		"colors": ["#1f4e8c"],
	}


def get_summary(data):
	depreciation = sum(r.depreciation for r in data)
	damage = sum(r.damage_cost for r in data)
	return [
		{"label": _("Depreciation"), "value": depreciation, "datatype": "Currency", "indicator": "Blue"},
		{"label": _("Damage Cost"), "value": damage, "datatype": "Currency", "indicator": "Red"},
		{
			"label": _("Total Cost"),
			"value": depreciation + damage,
			"datatype": "Currency",
			"indicator": "Green",
		},
		{"label": _("Projects"), "value": len({r.project for r in data}), "datatype": "Int"},
	]

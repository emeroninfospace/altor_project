# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Project assets: scaffolding materials and equipment issued to projects.

* A **Project Asset** is one purchase of an asset item (e.g. 100 Cuplock Standards 3.0m bought on one
  GRN) with its unit cost, salvage value and depreciation period in months.
* Per unit per day:  daily rate = (unit cost - salvage value) / (depreciation months x 30).
* An **Asset Allocation** issues quantities to a project. While the asset is on the project the project
  is charged  qty x daily rate x days  (delivery date to return date, both days counted, and not past
  the end of the depreciation period).
* An **Asset Return** brings quantities back. Damaged / lost quantities are written off and their book
  value on the return date (unit cost less depreciation since purchase, not below salvage) is charged to
  the project as damage cost.
* Depreciation and damage cost count against the Project Budget line of the asset's Item Group.
"""

import frappe
from frappe.utils import add_days, cint, date_diff, flt, getdate, nowdate

DAYS_PER_MONTH = 30


def daily_rate(unit_cost, salvage_value, months):
	"""Depreciation per unit per day."""
	months = cint(months)
	if months <= 0:
		return 0.0
	return max(flt(unit_cost) - flt(salvage_value), 0) / (months * DAYS_PER_MONTH)


def life_end(purchase_date, months):
	"""Last day the asset is depreciated."""
	if not purchase_date or cint(months) <= 0:
		return None
	return getdate(add_days(purchase_date, cint(months) * DAYS_PER_MONTH - 1))


def charge_days(start, end, until=None, period_start=None):
	"""Days charged from `start` to `end`, both included, cut at `until` (end of life) and `period_start`."""
	if not start or not end:
		return 0
	start, end = getdate(start), getdate(end)
	if until:
		end = min(end, getdate(until))
	if period_start:
		start = max(start, getdate(period_start))
	return max(date_diff(end, start) + 1, 0)


def book_value(unit_cost, salvage_value, months, purchase_date, on_date=None):
	"""Value of one unit on a date: cost less depreciation since purchase, not below salvage."""
	unit_cost, salvage_value = flt(unit_cost), flt(salvage_value)
	if not purchase_date or cint(months) <= 0:
		return unit_cost
	days = max(date_diff(on_date or nowdate(), purchase_date), 0)
	return max(unit_cost - daily_rate(unit_cost, salvage_value, months) * days, min(salvage_value, unit_cost))


def row_depreciation(row, delivery_date, as_of=None):
	"""Depreciation of an Asset Allocation row up to `as_of` (today by default).

	Quantities already back were charged up to their return date (returned_charge); what is still on
	the project is charged up to `as_of`.
	"""
	on_site = max(flt(row.get("qty")) - flt(row.get("returned_qty")) - flt(row.get("damaged_qty")), 0)
	open_days = charge_days(delivery_date, as_of or nowdate(), row.get("charge_until"))
	return flt(row.get("returned_charge")) + on_site * flt(row.get("daily_rate")) * open_days


# ---------------------------------------------------------------------------
# Quantities on the Project Asset
# ---------------------------------------------------------------------------


def update_asset_quantities(assets):
	"""Recalculate allocated / damaged / available quantities of Project Assets from the movements."""
	for name in {a for a in assets if a}:
		row = frappe.db.sql(
			"""
			SELECT SUM(i.qty - IFNULL(i.returned_qty, 0) - IFNULL(i.damaged_qty, 0)) AS on_site,
				SUM(IFNULL(i.damaged_qty, 0)) AS damaged
			FROM `tabAsset Allocation Item` i
			INNER JOIN `tabAsset Allocation` a ON a.name = i.parent
			WHERE a.docstatus = 1 AND i.project_asset = %s
			""",
			name,
			as_dict=True,
		)[0]
		qty = flt(frappe.db.get_value("Project Asset", name, "qty"))
		allocated, damaged = flt(row.on_site), flt(row.damaged)
		available = qty - allocated - damaged
		if available <= 0 and not allocated:
			status = "Written Off"
		elif not allocated:
			status = "Available"
		elif available <= 0:
			status = "Fully Allocated"
		else:
			status = "Partly Allocated"
		frappe.db.set_value(
			"Project Asset",
			name,
			{
				"allocated_qty": allocated,
				"damaged_qty": damaged,
				"available_qty": available,
				"status": status,
			},
			update_modified=False,
		)


STOCK_FIELDS = [
	"name",
	"asset",
	"asset_name",
	"item_group",
	"uom",
	"company",
	"purchase_date",
	"qty",
	"unit_cost",
	"daily_rate",
	"available_qty",
	"allocated_qty",
	"damaged_qty",
	"depreciation_end_date",
	"status",
]


def item_stock(item_code, company=None):
	"""All purchases (Project Assets) of one asset item taken together.

	Each purchase stays its own Project Asset (it is linked to its own Fixed Asset for the accounts);
	this adds them up: 4 bought at 300 and 5 at 250 -> 9 units, average unit cost
	(4 x 300 + 5 x 250) / 9 = 272.22. Averages are weighted by the quantity still owned
	(purchased less damaged / lost); the average daily rate is worked out the same way.
	"""
	filters = {"item_code": item_code, "disabled": 0}
	if company:
		filters["company"] = company
	lots = frappe.get_all(
		"Project Asset", filters=filters, fields=STOCK_FIELDS, order_by="purchase_date asc, creation asc"
	)
	out = frappe._dict(
		item_code=item_code,
		purchases=len(lots),
		qty=0.0,
		owned=0.0,
		available=0.0,
		on_projects=0.0,
		damaged=0.0,
		avg_unit_cost=0.0,
		avg_daily_rate=0.0,
		uom=lots[0].uom if lots else None,
		item_group=lots[0].item_group if lots else None,
		asset_name=lots[0].asset_name if lots else None,
		lots=lots,
	)
	cost = rate = 0.0
	for lot in lots:
		owned = max(flt(lot.qty) - flt(lot.damaged_qty), 0)
		out.qty += flt(lot.qty)
		out.owned += owned
		out.available += max(flt(lot.available_qty), 0)
		out.on_projects += flt(lot.allocated_qty)
		out.damaged += flt(lot.damaged_qty)
		cost += owned * flt(lot.unit_cost)
		rate += owned * flt(lot.daily_rate)
	if out.owned:
		out.avg_unit_cost = flt(cost / out.owned, 2)
		out.avg_daily_rate = flt(rate / out.owned, 4)
	return out


def lock_assets(assets):
	"""Lock Project Asset rows while quantities are checked and changed (concurrent issues)."""
	assets = sorted({a for a in assets if a})
	if assets:
		frappe.db.sql(
			"SELECT name FROM `tabProject Asset` WHERE name IN %s FOR UPDATE",
			(tuple(assets),),
		)


# ---------------------------------------------------------------------------
# Allocation figures (returns and depreciation to date)
# ---------------------------------------------------------------------------


def update_allocation(allocation, as_of=None):
	"""Write returned / damaged quantities and cost to date on a submitted Asset Allocation."""
	doc = frappe.get_doc("Asset Allocation", allocation)
	returns = {}
	for r in frappe.db.sql(
		"""
		SELECT ri.allocation_item, SUM(ri.returned_qty) AS returned_qty, SUM(ri.damaged_qty) AS damaged_qty,
			SUM(ri.depreciation_amount) AS charge, SUM(ri.damage_cost) AS damage_cost
		FROM `tabAsset Return Item` ri
		INNER JOIN `tabAsset Return` ar ON ar.name = ri.parent
		WHERE ar.docstatus = 1 AND ar.asset_allocation = %s
		GROUP BY ri.allocation_item
		""",
		allocation,
		as_dict=True,
	):
		returns[r.allocation_item] = r

	totals = frappe._dict(on_site=0, depreciation=0, damage=0)
	for row in doc.items:
		back = returns.get(row.name) or frappe._dict()
		row.returned_qty = flt(back.returned_qty)
		row.damaged_qty = flt(back.damaged_qty)
		row.returned_charge = flt(back.charge, 2)
		row.damage_cost = flt(back.damage_cost, 2)
		row.on_site_qty = max(flt(row.qty) - row.returned_qty - row.damaged_qty, 0)
		row.depreciation_to_date = flt(row_depreciation(row, doc.delivery_date, as_of), 2)
		totals.on_site += row.on_site_qty
		totals.depreciation += row.depreciation_to_date
		totals.damage += row.damage_cost
		frappe.db.set_value(
			"Asset Allocation Item",
			row.name,
			{
				f: row.get(f)
				for f in (
					"returned_qty",
					"damaged_qty",
					"returned_charge",
					"damage_cost",
					"on_site_qty",
					"depreciation_to_date",
				)
			},
			update_modified=False,
		)

	total_qty = sum(flt(r.qty) for r in doc.items)
	if totals.on_site <= 0:
		status = "Returned"
	elif totals.on_site < total_qty:
		status = "Partly Returned"
	else:
		status = "Allocated"
	frappe.db.set_value(
		"Asset Allocation",
		doc.name,
		{
			"on_site_qty": totals.on_site,
			"depreciation_to_date": flt(totals.depreciation, 2),
			"total_damage_cost": flt(totals.damage, 2),
			"total_project_cost": flt(totals.depreciation + totals.damage, 2),
			"status": status,
		},
		update_modified=False,
	)
	return doc


def refresh_open_allocations():
	"""Daily job: bring "cost to date" up to today on allocations that still have assets on site."""
	for name in frappe.get_all(
		"Asset Allocation", filters={"docstatus": 1, "status": ["!=", "Returned"]}, pluck="name"
	):
		try:
			update_allocation(name)
		except Exception:
			frappe.log_error(title=f"Asset Allocation refresh failed for {name}")


# ---------------------------------------------------------------------------
# Project budget
# ---------------------------------------------------------------------------


def get_asset_cost(project, as_of=None):
	"""{item_group: {"depreciation": x, "damage": y}} for a project's submitted allocations."""
	out = {}
	if not project or not frappe.db.table_exists("Asset Allocation Item"):
		return out
	rows = frappe.db.sql(
		"""
		SELECT i.item_group, i.qty, i.returned_qty, i.damaged_qty, i.daily_rate, i.returned_charge,
			i.damage_cost, i.charge_until, a.delivery_date
		FROM `tabAsset Allocation Item` i
		INNER JOIN `tabAsset Allocation` a ON a.name = i.parent
		WHERE a.docstatus = 1 AND a.project = %s
		""",
		project,
		as_dict=True,
	)
	for row in rows:
		group = out.setdefault(row.item_group or "", {"depreciation": 0.0, "damage": 0.0})
		group["depreciation"] += row_depreciation(row, row.delivery_date, as_of)
		group["damage"] += flt(row.damage_cost)
	return out


def on_movement(doc, assets):
	"""After an allocation / return is submitted or cancelled: quantities, figures and budget."""
	from altor_project.budget import queue_budget_update

	update_asset_quantities(assets)
	queue_budget_update(doc.project)

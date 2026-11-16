# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

from altor_project.assets import book_value, charge_days, lock_assets, on_movement, update_allocation


class AssetReturn(Document):
	def validate(self):
		allocation = frappe.get_doc("Asset Allocation", self.asset_allocation)
		if allocation.docstatus != 1:
			frappe.throw(_("Asset Allocation {0} is not submitted.").format(self.asset_allocation))
		for field in ("project", "project_name", "company", "cost_center", "delivery_date"):
			self.set(field, allocation.get(field))
		if getdate(self.return_date) < getdate(allocation.delivery_date):
			frappe.throw(_("Return Date cannot be before the Delivery Date."))
		if getdate(self.return_date) > getdate(nowdate()):
			frappe.throw(_("Return Date cannot be in the future."))
		self.set_rows(allocation)

	def before_submit(self):
		lock_assets([row.project_asset for row in self.items])
		self.set_rows(frappe.get_doc("Asset Allocation", self.asset_allocation))

	def on_submit(self):
		self.update_movement()

	def on_cancel(self):
		self.update_movement()

	def update_movement(self):
		update_allocation(self.asset_allocation)
		on_movement(self, [row.project_asset for row in self.items])

	def already_back(self):
		"""{allocation row: qty returned or damaged on other submitted returns}."""
		return dict(
			frappe.db.sql(
				"""
				SELECT ri.allocation_item, SUM(ri.returned_qty + ri.damaged_qty)
				FROM `tabAsset Return Item` ri
				INNER JOIN `tabAsset Return` ar ON ar.name = ri.parent
				WHERE ar.docstatus = 1 AND ar.asset_allocation = %s AND ar.name != %s
				GROUP BY ri.allocation_item
				""",
				(self.asset_allocation, self.name or ""),
			)
		)

	def set_rows(self, allocation):
		alloc_rows = {row.name: row for row in allocation.items}
		back = self.already_back()
		assets = {
			a.name: a
			for a in frappe.get_all(
				"Project Asset",
				filters={"name": ["in", list({r.project_asset for r in allocation.items})]},
				fields=["name", "unit_cost", "salvage_value", "depreciation_months", "purchase_date"],
			)
		}
		taken = {}
		totals = frappe._dict(returned=0, damaged=0, depreciation=0, damage=0)
		for row in self.items:
			source = alloc_rows.get(row.allocation_item)
			if not source:
				# row added by hand: take the first allocation row of that asset
				source = next((r for r in allocation.items if r.project_asset == row.project_asset), None)
				if not source:
					frappe.throw(
						_("Row #{0}: {1} is not on allocation {2}.").format(
							row.idx, row.project_asset, allocation.name
						)
					)
				row.allocation_item = source.name

			on_site = flt(source.qty) - flt(back.get(source.name)) - taken.get(source.name, 0)
			qty_back = flt(row.returned_qty) + flt(row.damaged_qty)
			if flt(row.returned_qty) < 0 or flt(row.damaged_qty) < 0:
				frappe.throw(_("Row #{0}: quantities cannot be negative.").format(row.idx))
			if qty_back > on_site + 1e-9:
				frappe.throw(
					_("Row #{0}: {1} returned + damaged is more than the {2} still on site.").format(
						row.idx, qty_back, on_site
					)
				)
			taken[source.name] = taken.get(source.name, 0) + qty_back

			row.project_asset = source.project_asset
			row.asset_name = source.asset_name
			row.item_code = source.item_code
			row.item_group = source.item_group
			row.uom = source.uom
			row.on_site_qty = on_site
			row.daily_rate = flt(source.daily_rate, 4)
			row.days = charge_days(allocation.delivery_date, self.return_date, source.charge_until)
			row.depreciation_amount = flt(qty_back * row.daily_rate * row.days, 2)

			asset = assets.get(source.project_asset) or frappe._dict()
			row.book_value = flt(
				book_value(
					asset.unit_cost,
					asset.salvage_value,
					asset.depreciation_months,
					asset.purchase_date,
					self.return_date,
				),
				2,
			)
			if flt(row.damaged_qty) and not flt(row.damage_rate):
				row.damage_rate = row.book_value
			row.damage_cost = flt(flt(row.damaged_qty) * flt(row.damage_rate), 2)

			totals.returned += flt(row.returned_qty)
			totals.damaged += flt(row.damaged_qty)
			totals.depreciation += row.depreciation_amount
			totals.damage += row.damage_cost

		if not totals.returned and not totals.damaged:
			frappe.throw(_("Enter the returned or damaged quantity."))
		self.total_returned_qty = totals.returned
		self.total_damaged_qty = totals.damaged
		self.total_depreciation = flt(totals.depreciation, 2)
		self.total_damage_cost = flt(totals.damage, 2)
		self.total_cost = flt(totals.depreciation + totals.damage, 2)

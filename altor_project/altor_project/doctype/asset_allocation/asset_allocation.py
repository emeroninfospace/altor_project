# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from altor_project.asset_accounting import ENDED, asset_state
from altor_project.assets import item_stock, lock_assets, on_movement, update_allocation


class AssetAllocation(Document):
	def validate(self):
		if self.docstatus == 0:
			self.status = "Draft"
		self.validate_project()
		self.expand_item_rows()
		self.set_rows()
		if self.docstatus == 0:
			self.check_available(throw=False)

	def before_submit(self):
		lock_assets([row.project_asset for row in self.items])
		self.check_available(throw=True)

	def on_submit(self):
		update_allocation(self.name)
		on_movement(self, [row.project_asset for row in self.items])

	def before_cancel(self):
		returns = frappe.get_all(
			"Asset Return", filters={"asset_allocation": self.name, "docstatus": 1}, pluck="name"
		)
		if returns:
			frappe.throw(
				_("Cancel the Asset Returns made against this allocation first: {0}").format(
					", ".join(returns)
				)
			)

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
		on_movement(self, [row.project_asset for row in self.items])

	def validate_project(self):
		status = frappe.db.get_value("Project", self.project, "status")
		if status in ("Completed", "Cancelled"):
			frappe.throw(
				_("Project {0} is {1}. Assets cannot be issued to it.").format(self.project, _(status))
			)

	def expand_item_rows(self):
		"""A row with only an Item issues from that item's purchases, oldest first: it becomes one row
		per Project Asset used (4 from the first purchase, 3 from the next...)."""
		if not any(row.item_code and not row.project_asset for row in self.items):
			return
		taken = {}
		for row in self.items:
			if row.project_asset:
				taken[row.project_asset] = taken.get(row.project_asset, 0) + flt(row.qty)
		rows = []
		for row in self.items:
			if row.project_asset or not row.item_code:
				rows.append(row)
				continue
			need = flt(row.qty)
			if need <= 0:
				frappe.throw(_("Row #{0}: Qty must be more than 0.").format(row.idx))
			for lot in issue_lots(row.item_code, self.company, self.delivery_date):
				free = flt(lot.available_qty) - taken.get(lot.name, 0)
				if free <= 1e-9:
					continue
				use = min(free, need)
				rows.append({"project_asset": lot.name, "item_code": row.item_code, "qty": use})
				taken[lot.name] = taken.get(lot.name, 0) + use
				need -= use
				if need <= 1e-9:
					break
			if need > 1e-9:
				stock = item_stock(row.item_code, self.company)
				frappe.throw(
					_("Row #{0}: only {1} {2} of {3} available (issuing {4}).").format(
						row.idx,
						flt(row.qty) - need,
						stock.uom or "",
						stock.asset_name or row.item_code,
						flt(row.qty),
					),
					title=_("Insufficient Quantity"),
				)
		self.set("items", [])
		for row in rows:
			self.append("items", row)

	def set_rows(self):
		if not self.items:
			frappe.throw(_("Add the assets to issue."))
		names = list({row.project_asset for row in self.items if row.project_asset})
		assets = {
			a.name: a
			for a in frappe.get_all(
				"Project Asset",
				filters={"name": ["in", names]},
				fields=[
					"name",
					"asset_name",
					"item_code",
					"item_group",
					"uom",
					"company",
					"disabled",
					"purchase_date",
					"daily_rate",
					"depreciation_end_date",
					"available_qty",
				],
			)
		}
		stocks = {}
		total_qty = daily = 0
		for row in self.items:
			asset = assets.get(row.project_asset)
			if not asset:
				frappe.throw(_("Row #{0}: select a Project Asset.").format(row.idx))
			if asset.disabled:
				frappe.throw(_("Row #{0}: Project Asset {1} is disabled.").format(row.idx, asset.name))
			linked, status, _docstatus = asset_state(asset.name)
			if status in ENDED:
				frappe.throw(
					_("Row #{0}: Fixed Asset {1} of {2} is {3}.").format(
						row.idx, linked, asset.name, _(status)
					)
				)
			if self.company and asset.company and asset.company != self.company:
				frappe.throw(
					_("Row #{0}: {1} belongs to {2}, not {3}.").format(
						row.idx, asset.name, asset.company, self.company
					)
				)
			if flt(row.qty) <= 0:
				frappe.throw(_("Row #{0}: Qty must be more than 0.").format(row.idx))
			if asset.purchase_date and getdate(self.delivery_date) < getdate(asset.purchase_date):
				frappe.throw(
					_("Row #{0}: {1} was purchased on {2}, after the delivery date.").format(
						row.idx, asset.asset_name, frappe.format(asset.purchase_date, "Date")
					)
				)
			# all purchases of an item are charged at the item's average rate (weighted by quantity);
			# rate and depreciation end are fixed when the asset is issued (validate does not run after submit)
			if asset.item_code not in stocks:
				stocks[asset.item_code] = item_stock(asset.item_code, asset.company)
			stock = stocks[asset.item_code]
			row.daily_rate = flt(stock.avg_daily_rate if stock.owned else asset.daily_rate, 4)
			row.charge_until = asset.depreciation_end_date
			row.available_qty = flt(stock.available)
			row.asset_name = asset.asset_name
			row.item_code = asset.item_code
			row.item_group = asset.item_group
			row.uom = asset.uom
			row.daily_amount = flt(flt(row.qty) * flt(row.daily_rate), 2)
			total_qty += flt(row.qty)
			daily += row.daily_amount
		self.total_qty = total_qty
		self.daily_charge = flt(daily, 2)

	def check_available(self, throw):
		wanted = {}
		for row in self.items:
			wanted[row.project_asset] = wanted.get(row.project_asset, 0) + flt(row.qty)
		available = dict(
			frappe.get_all(
				"Project Asset",
				filters={"name": ["in", list(wanted)]},
				fields=["name", "available_qty"],
				as_list=True,
			)
		)
		short = [
			_("{0}: issuing {1}, available {2}").format(name, qty, flt(available.get(name)))
			for name, qty in wanted.items()
			if qty > flt(available.get(name)) + 1e-9
		]
		if not short:
			return
		message = _("Not enough quantity available:") + "<br>" + "<br>".join(short)
		if throw:
			frappe.throw(message, title=_("Insufficient Quantity"))
		frappe.msgprint(message, title=_("Insufficient Quantity"), indicator="orange")


def issue_lots(item_code, company, delivery_date=None):
	"""Project Assets of an item that can be issued, oldest purchase first."""
	lots = []
	for lot in item_stock(item_code, company).lots:
		if flt(lot.available_qty) <= 0:
			continue
		if delivery_date and lot.purchase_date and getdate(lot.purchase_date) > getdate(delivery_date):
			continue
		if asset_state(lot.name)[1] in ENDED:
			continue
		lots.append(lot)
	return lots


@frappe.whitelist()
def get_item_stock(item_code, company=None):
	"""Available quantity and average rates of an asset item over all its purchases."""
	frappe.has_permission("Project Asset", "read", throw=True)
	return item_stock(item_code, company)


@frappe.whitelist()
def make_asset_return(source_name):
	"""New Asset Return with everything still on site (button on the allocation)."""
	frappe.has_permission("Asset Return", "create", throw=True)
	allocation = frappe.get_doc("Asset Allocation", source_name)
	allocation.check_permission("read")
	if allocation.docstatus != 1:
		frappe.throw(_("Submit the Asset Allocation first."))
	doc = frappe.new_doc("Asset Return")
	doc.asset_allocation = allocation.name
	for field in ("project", "project_name", "company", "cost_center", "delivery_date"):
		doc.set(field, allocation.get(field))
	for row in allocation.items:
		on_site = flt(row.qty) - flt(row.returned_qty) - flt(row.damaged_qty)
		if on_site > 0:
			doc.append(
				"items",
				{
					"allocation_item": row.name,
					"project_asset": row.project_asset,
					"asset_name": row.asset_name,
					"uom": row.uom,
					"on_site_qty": on_site,
					"returned_qty": on_site,
					"damaged_qty": 0,
					"daily_rate": row.daily_rate,
				},
			)
	if not doc.items:
		frappe.throw(_("Everything on {0} has already been returned.").format(allocation.name))
	return doc


@frappe.whitelist()
def refresh_figures(name):
	"""Recalculate cost to date (button on the allocation)."""
	frappe.get_doc("Asset Allocation", name).check_permission("read")
	update_allocation(name)
	return True

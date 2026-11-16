# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from altor_project.assets import lock_assets, on_movement, update_allocation


class AssetAllocation(Document):
	def validate(self):
		if self.docstatus == 0:
			self.status = "Draft"
		self.validate_project()
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
		total_qty = daily = 0
		for row in self.items:
			asset = assets.get(row.project_asset)
			if not asset:
				frappe.throw(_("Row #{0}: select a Project Asset.").format(row.idx))
			if asset.disabled:
				frappe.throw(_("Row #{0}: Project Asset {1} is disabled.").format(row.idx, asset.name))
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
			# rate and depreciation end are fixed when the asset is issued (validate does not run after submit)
			row.daily_rate = flt(asset.daily_rate, 4)
			row.charge_until = asset.depreciation_end_date
			row.available_qty = flt(asset.available_qty)
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

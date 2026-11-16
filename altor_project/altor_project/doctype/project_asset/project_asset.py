# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, nowdate

from altor_project.assets import DAYS_PER_MONTH, book_value, daily_rate, life_end, row_depreciation


class ProjectAsset(Document):
	def validate(self):
		self.sync_from_asset()
		if not self.company:
			self.company = frappe.defaults.get_user_default("Company") or frappe.defaults.get_global_default(
				"company"
			)
		if not self.asset_name and self.item_code:
			self.asset_name = frappe.db.get_value("Item", self.item_code, "item_name")
		if flt(self.qty) <= 0:
			frappe.throw(_("Quantity Purchased must be more than 0."))
		if cint(self.depreciation_months) <= 0 and not self.asset:
			# a linked Asset without depreciation is charged to projects at 0 per day
			frappe.throw(_("Enter the Depreciation Period in months."))
		if flt(self.salvage_value) > flt(self.unit_cost):
			frappe.throw(_("Salvage Value cannot be more than the Unit Cost."))

		self.total_cost = flt(flt(self.qty) * flt(self.unit_cost), 2)
		self.daily_rate = flt(daily_rate(self.unit_cost, self.salvage_value, self.depreciation_months), 4)
		self.monthly_rate = flt(self.daily_rate * DAYS_PER_MONTH, 2)
		self.depreciation_end_date = life_end(self.purchase_date, self.depreciation_months)

		moved = flt(self.allocated_qty) + flt(self.damaged_qty)
		if flt(self.qty) < moved:
			frappe.throw(
				_("Quantity cannot be less than {0}: {1} is on projects and {2} is damaged / lost.").format(
					moved, flt(self.allocated_qty), flt(self.damaged_qty)
				)
			)
		self.available_qty = flt(self.qty) - moved
		if self.is_new():
			self.status = "Available"
		elif not self.flags.ignore_rate_warning and self.has_value_changed("daily_rate") and moved:
			frappe.msgprint(
				_(
					"The new rate applies to future allocations. Assets already on projects keep the rate they were issued with."
				),
				indicator="orange",
				alert=True,
			)

	def sync_from_asset(self):
		"""A linked ERPNext Asset is the source of the cost, quantity and depreciation."""
		if not self.asset:
			return
		from altor_project.asset_accounting import has_movements, values_from_asset

		asset = frappe.get_doc("Asset", self.asset)
		if asset.docstatus == 2:
			frappe.throw(_("Asset {0} is cancelled.").format(self.asset))
		other = frappe.db.get_value("Project Asset", {"asset": self.asset, "name": ["!=", self.name or ""]})
		if other:
			frappe.throw(_("Asset {0} is already linked to Project Asset {1}.").format(self.asset, other))
		values = values_from_asset(asset)
		if not self.is_new() and has_movements(self.name):
			# issued to projects: the quantity stays as issued (a later split / scrap changes the Asset's)
			values.pop("qty")
			if self.has_value_changed("asset"):
				frappe.throw(
					_("The ERPNext Asset cannot be changed once the asset has been issued to projects.")
				)
		self.update(values)

	def onload(self):
		self.set_onload("book_value", flt(self.get_book_value(), 2))
		self.set_onload("on_projects", self.get_on_projects())

	def get_book_value(self, on_date=None):
		return book_value(
			self.unit_cost,
			self.salvage_value,
			self.depreciation_months,
			self.purchase_date,
			on_date or nowdate(),
		)

	def get_on_projects(self):
		rows = frappe.db.sql(
			"""
			SELECT a.name AS allocation, a.project, a.project_name, a.delivery_date, i.qty, i.returned_qty,
				i.damaged_qty, i.daily_rate, i.returned_charge, i.charge_until
			FROM `tabAsset Allocation Item` i
			INNER JOIN `tabAsset Allocation` a ON a.name = i.parent
			WHERE a.docstatus = 1 AND i.project_asset = %s
				AND i.qty - IFNULL(i.returned_qty, 0) - IFNULL(i.damaged_qty, 0) > 0
			ORDER BY a.delivery_date
			""",
			self.name,
			as_dict=True,
		)
		for row in rows:
			row.on_site = flt(row.qty) - flt(row.returned_qty) - flt(row.damaged_qty)
			row.depreciation = flt(row_depreciation(row, row.delivery_date), 2)
		return rows

# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Purchase Receipt (GRN): items marked "Project Asset" become Project Assets on submit.

The purchase price comes from the GRN row and the depreciation period from the row (defaulted
from the Item), so both are set during GRN entry.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt


def _asset_items(doc):
	codes = list({row.item_code for row in doc.get("items") or [] if row.get("item_code")})
	if not codes or not frappe.db.has_column("Item", "custom_is_project_asset"):
		return {}
	return {
		i.name: i
		for i in frappe.get_all(
			"Item",
			filters={"name": ["in", codes], "custom_is_project_asset": 1},
			fields=["name", "item_name", "item_group", "stock_uom", "custom_depreciation_months"],
		)
	}


def validate(doc, method=None):
	items = _asset_items(doc)
	missing = []
	for row in doc.get("items") or []:
		item = items.get(row.item_code)
		if not item:
			continue
		if not cint(row.get("custom_depreciation_months")):
			row.custom_depreciation_months = cint(item.custom_depreciation_months)
		if not cint(row.get("custom_depreciation_months")):
			missing.append(_("Row #{0}: {1}").format(row.idx, row.item_code))
	if missing:
		frappe.throw(
			_("Enter the Depreciation Period (Months) for these project assets:")
			+ "<br>"
			+ "<br>".join(missing),
			title=_("Depreciation Missing"),
		)


def on_submit(doc, method=None):
	items = _asset_items(doc)
	created = []
	for row in doc.get("items") or []:
		item = items.get(row.item_code)
		qty = flt(row.get("stock_qty")) or flt(row.qty)
		if not item or qty <= 0:
			continue
		asset = frappe.new_doc("Project Asset")
		asset.update(
			{
				"asset_name": row.item_name or item.item_name,
				"item_code": row.item_code,
				"item_group": item.item_group,
				"company": doc.company,
				"cost_center": row.get("cost_center") or doc.get("cost_center"),
				"uom": item.stock_uom or row.uom,
				"purchase_date": doc.posting_date,
				"supplier": doc.supplier,
				"purchase_receipt": doc.name,
				"purchase_receipt_item": row.name,
				"qty": qty,
				"unit_cost": flt(row.base_net_amount) / qty,
				"depreciation_months": cint(row.custom_depreciation_months)
				or cint(item.custom_depreciation_months),
			}
		)
		asset.insert(ignore_permissions=True)
		created.append(frappe.utils.get_link_to_form("Project Asset", asset.name))
	if created:
		frappe.msgprint(
			_("Project Assets created: {0}").format(", ".join(created)),
			title=_("Project Assets"),
			indicator="green",
		)


def before_cancel(doc, method=None):
	assets = frappe.get_all(
		"Project Asset",
		filters={"purchase_receipt": doc.name},
		fields=["name", "allocated_qty", "damaged_qty"],
	)
	used = [a.name for a in assets if flt(a.allocated_qty) or flt(a.damaged_qty) or _has_movements(a.name)]
	if used:
		frappe.throw(
			_("These Project Assets from this receipt have been issued to projects: {0}").format(
				", ".join(used)
			),
			title=_("Assets in Use"),
		)


def on_cancel(doc, method=None):
	for name in frappe.get_all("Project Asset", filters={"purchase_receipt": doc.name}, pluck="name"):
		frappe.delete_doc("Project Asset", name, ignore_permissions=True, force=True)


def _has_movements(asset):
	return bool(
		frappe.db.sql(
			"""
			SELECT i.name FROM `tabAsset Allocation Item` i
			INNER JOIN `tabAsset Allocation` a ON a.name = i.parent
			WHERE i.project_asset = %s AND a.docstatus < 2 LIMIT 1
			""",
			asset,
		)
	)

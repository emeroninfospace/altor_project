# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Project Assets on top of ERPNext's Asset module.

ERPNext keeps the accounts, our Project Asset keeps the site and project side:

* An Item ticked "Project Asset" is a fixed asset item (Is Fixed Asset, Asset Category, Create Grouped
  Asset). A GRN / purchase invoice of it creates ONE ERPNext Asset for the whole quantity (standard).
* When that Asset is submitted, a Project Asset is created and linked to it: quantity, cost, salvage
  value and depreciation period come from the Asset (its first finance book).
* ERPNext posts the depreciation (monthly journal entries), sells, splits and scraps the Asset as usual.
* Damaged / lost quantities on an Asset Return are written off with ERPNext's own Split Asset +
  Scrap Asset (Altor Settings > Write Off Damaged Assets); cancelling the return restores them.
* Month end: a Journal Entry moves the depreciation of the assets used on projects from the asset's
  cost center to each project and its division (same figures as the Project Asset Cost report).

None of this blocks a standard ERPNext document: when a link cannot be made, the user gets a message.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, get_first_day, get_last_day, get_link_to_form, getdate, nowdate

ENDED = ("Scrapped", "Sold", "Cancelled", "Capitalized", "Decapitalized")


def _setting(field, default=0):
	value = frappe.get_cached_doc("Altor Settings").get(field)
	return default if value is None else cint(value)


def is_project_asset_item(item_code):
	return bool(
		item_code
		and frappe.db.has_column("Item", "custom_is_project_asset")
		and frappe.db.get_value("Item", item_code, "custom_is_project_asset")
	)


# ---------------------------------------------------------------------------
# ERPNext Asset -> Project Asset
# ---------------------------------------------------------------------------


def values_from_asset(asset):
	"""Project Asset values taken from an ERPNext Asset (its first finance book)."""
	qty = flt(asset.get("asset_quantity")) or 1
	book = (asset.get("finance_books") or [None])[0] if cint(asset.get("calculate_depreciation")) else None
	months = (
		cint(book.total_number_of_depreciations) * (cint(book.frequency_of_depreciation) or 1) if book else 0
	)
	return {
		"asset_name": asset.asset_name,
		"item_code": asset.item_code,
		"company": asset.company,
		"cost_center": asset.get("cost_center"),
		"purchase_date": asset.get("available_for_use_date") or asset.purchase_date,
		"purchase_receipt": asset.get("purchase_receipt"),
		"qty": qty,
		"unit_cost": flt(asset.get("gross_purchase_amount")) / qty,
		"salvage_value": flt(book.expected_value_after_useful_life) / qty if book else 0,
		"depreciation_months": months,
	}


def on_asset_submit(doc, method=None):
	"""doc_event (Asset on_submit): a project asset item gets its Project Asset."""
	if (
		frappe.flags.altor_asset_write_off
		or doc.get("split_from")  # a split keeps the Project Asset of the asset it came from
		or not is_project_asset_item(doc.item_code)
		or frappe.db.exists("Project Asset", {"asset": doc.name})
	):
		return
	frappe.db.savepoint("altor_project_asset")
	try:
		pa = frappe.new_doc("Project Asset")
		pa.asset = doc.name
		pa.update(values_from_asset(doc))
		pa.flags.ignore_permissions = True
		pa.insert()
		frappe.msgprint(
			_("Project Asset {0} created for issuing this asset to projects.").format(
				get_link_to_form("Project Asset", pa.name)
			),
			alert=True,
			indicator="green",
		)
	except Exception as e:
		frappe.db.rollback(save_point="altor_project_asset")
		frappe.log_error(title=f"Project Asset not created for {doc.name}")
		frappe.msgprint(
			_("Project Asset not created for {0}: {1}. Create it from Project Asset > New.").format(
				doc.name, frappe.utils.strip_html(str(e))
			),
			indicator="orange",
		)


def has_movements(project_asset):
	return bool(
		frappe.db.exists("Asset Allocation Item", {"project_asset": project_asset, "docstatus": ["<", 2]})
	)


def on_asset_cancel(doc, method=None):
	"""doc_event (Asset on_cancel): remove an unused Project Asset, otherwise disable it."""
	for name in frappe.get_all("Project Asset", filters={"asset": doc.name}, pluck="name"):
		if has_movements(name):
			frappe.db.set_value("Project Asset", name, "disabled", 1)
			frappe.msgprint(
				_("Project Asset {0} has been issued to projects, so it is kept and disabled.").format(name),
				indicator="orange",
			)
		else:
			frappe.delete_doc("Project Asset", name, ignore_permissions=True, force=True)


def asset_state(project_asset):
	"""(asset name, status, docstatus) of the ERPNext Asset linked to a Project Asset."""
	asset = frappe.db.get_value("Project Asset", project_asset, "asset")
	if not asset:
		return None, None, None
	status, docstatus = frappe.db.get_value("Asset", asset, ["status", "docstatus"]) or (None, None)
	return asset, status, docstatus


# ---------------------------------------------------------------------------
# Damaged / lost on an Asset Return -> ERPNext Split Asset + Scrap Asset
# ---------------------------------------------------------------------------


def write_off_damaged(ret):
	"""On Asset Return submit: scrap the damaged quantity of the linked ERPNext Assets."""
	if not _setting("write_off_damaged_assets", 1):
		return
	from erpnext.assets.doctype.asset.asset import split_asset
	from erpnext.assets.doctype.asset.depreciation import scrap_asset

	for row in ret.items:
		damaged = flt(row.damaged_qty)
		asset, status, docstatus = asset_state(row.project_asset)
		if not damaged or not asset:
			continue
		if docstatus != 1 or status in ENDED:
			frappe.msgprint(
				_(
					"Row #{0}: Asset {1} is {2}; the damaged quantity is not written off in the accounts."
				).format(row.idx, asset, _(status or "Draft")),
				indicator="orange",
			)
			continue
		qty, asset_qty = cint(damaged), cint(frappe.db.get_value("Asset", asset, "asset_quantity")) or 1
		if qty != damaged or qty > asset_qty:
			frappe.msgprint(
				_("Row #{0}: {1} damaged cannot be written off from Asset {2} ({3} units).").format(
					row.idx, damaged, asset, asset_qty
				),
				indicator="orange",
			)
			continue
		frappe.flags.altor_asset_write_off = True
		try:
			target = asset if qty == asset_qty else split_asset(asset, qty)
			target = getattr(target, "name", target)
			scrap_asset(target)
		except frappe.ValidationError as e:
			frappe.throw(
				_(
					"Row #{0}: the damaged quantity could not be written off in the accounts: {1}<br>Set the company's asset accounts (Company > Accounts > Gain/Loss Account on Asset Disposal), or untick Write Off Damaged Assets in Altor Settings."
				).format(row.idx, frappe.utils.strip_html(str(e))),
				title=_("Asset Write-off"),
			)
		finally:
			frappe.flags.altor_asset_write_off = False
		row.db_set("written_off_asset", target, update_modified=False)


def restore_written_off(ret):
	"""On Asset Return cancel: bring the scrapped quantity back (ERPNext Restore Asset)."""
	from erpnext.assets.doctype.asset.depreciation import restore_asset

	for row in ret.items:
		if (
			row.get("written_off_asset")
			and frappe.db.get_value("Asset", row.written_off_asset, "status") == "Scrapped"
		):
			restore_asset(row.written_off_asset)
			frappe.msgprint(
				_("Asset {0} restored. It stays a separate asset of {1} units.").format(
					row.written_off_asset, flt(row.damaged_qty)
				),
				indicator="blue",
			)


# ---------------------------------------------------------------------------
# Month end: depreciation of project assets -> projects (Journal Entry)
# ---------------------------------------------------------------------------


def _period_dates(period):
	start = getdate(f"{period}-01")
	return start, getdate(get_last_day(start))


def allocation_lines(company, from_date, to_date):
	"""[(expense account, asset cost center, project, division, amount)] for linked, submitted assets."""
	from altor_project.altor_project.report.project_asset_cost.project_asset_cost import get_data

	rows = get_data(frappe._dict(company=company, from_date=from_date, to_date=to_date))
	if not rows:
		return []
	project_assets = {r.project_asset for r in rows}
	links = dict(
		frappe.get_all(
			"Project Asset",
			filters={"name": ["in", list(project_assets)]},
			fields=["name", "asset"],
			as_list=True,
		)
	)
	company_doc = frappe.get_cached_doc("Company", company)
	assets = {}
	for name in {a for a in links.values() if a}:
		a = frappe.db.get_value(
			"Asset", name, ["docstatus", "asset_category", "cost_center", "company"], as_dict=True
		)
		if not a or a.docstatus != 1:
			continue
		account = frappe.db.get_value(
			"Asset Category Account",
			{"parent": a.asset_category, "company_name": a.company},
			"depreciation_expense_account",
		)
		assets[name] = (
			account or company_doc.depreciation_expense_account,
			a.cost_center or company_doc.depreciation_cost_center or company_doc.cost_center,
		)
	divisions = dict(
		frappe.get_all(
			"Asset Allocation",
			filters={"name": ["in", list({r.allocation for r in rows})]},
			fields=["name", "cost_center"],
			as_list=True,
		)
	)
	out = {}
	for r in rows:
		linked = assets.get(links.get(r.project_asset))
		if not linked or not flt(r.depreciation):
			continue
		account, source = linked
		division = (
			divisions.get(r.allocation) or frappe.db.get_value("Project", r.project, "cost_center") or source
		)
		key = (account, source, r.project, division)
		out[key] = out.get(key, 0) + flt(r.depreciation)
	return [(*k, flt(v, 2)) for k, v in out.items() if flt(v, 2)]


def posted_allocation(company, period):
	return frappe.db.get_value(
		"Journal Entry",
		{"company": company, "custom_asset_depreciation_period": period, "docstatus": 1},
		"name",
	)


@frappe.whitelist()
def post_depreciation_allocation(company, period):
	"""Journal Entry moving a finished month's project asset depreciation to the projects."""
	frappe.has_permission("Journal Entry", "create", throw=True)
	start, end = _period_dates(period)
	if end >= getdate(nowdate()):
		frappe.throw(_("Post a month once it has ended ({0} ends on {1}).").format(period, end))
	existing = posted_allocation(company, period)
	if existing:
		return {"journal_entry": existing, "existing": True}
	lines = allocation_lines(company, start, end)
	if not lines:
		return {
			"journal_entry": None,
			"message": _("No depreciation of linked project assets in {0}.").format(period),
		}

	je = frappe.new_doc("Journal Entry")
	je.update(
		{
			# ERPNext requires this type on entries that touch a depreciation account; with no Asset
			# reference on the rows it does not change any asset's value
			"voucher_type": "Depreciation Entry",
			"company": company,
			"posting_date": end,
			"custom_asset_depreciation_period": period,
			"user_remark": _(
				"Depreciation of project assets for {0}, moved from the asset cost centers to the projects using them."
			).format(period),
		}
	)
	credits = {}
	for account, source, project, division, amount in lines:
		je.append(
			"accounts",
			{
				"account": account,
				"debit_in_account_currency": amount,
				"project": project,
				"cost_center": division,
			},
		)
		credits[(account, source)] = credits.get((account, source), 0) + amount
	for (account, source), amount in credits.items():
		je.append(
			"accounts",
			{"account": account, "credit_in_account_currency": flt(amount, 2), "cost_center": source},
		)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	return {"journal_entry": je.name, "existing": False}


def scheduled_allocation():
	"""Monthly job: post last month's allocation when Altor Settings asks for it."""
	if not _setting("auto_post_asset_depreciation", 0):
		return
	period = str(add_days(get_first_day(nowdate()), -1))[:7]
	for company in frappe.get_all("Company", pluck="name"):
		try:
			post_depreciation_allocation(company, period)
		except Exception:
			frappe.log_error(title=f"Project asset depreciation allocation failed: {company} {period}")


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------


def validate_item(doc, method=None):
	"""doc_event (Item validate): a Project Asset item is an ERPNext fixed asset item."""
	if doc.get("custom_is_project_asset") and not doc.get("is_fixed_asset"):
		frappe.throw(
			_(
				"A Project Asset item must be a fixed asset: tick Is Fixed Asset and choose its Asset Category."
			),
			title=_("Project Asset"),
		)

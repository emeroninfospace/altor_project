# Copyright (c) 2025, Emeron

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}

	if filters.get("from_date") and filters.get("to_date"):
		if filters.get("from_date") > filters.get("to_date"):
			frappe.throw(_("From Date must be before To Date"))

	columns = get_columns()
	data = get_data(filters)
	summary = get_summary(data)

	return columns, data, None, None, summary


# ═══════════════════════════════════════════════════════════════
# DATA
# ═══════════════════════════════════════════════════════════════


def get_data(filters):
	ee = frappe.qb.DocType("Expense Entry")
	eei = frappe.qb.DocType("Expense Entry Item")
	proj = frappe.qb.DocType("Project")  # ✅ NEW

	query = (
		frappe.qb.from_(ee)
		.inner_join(eei)
		.on(ee.name == eei.parent)
		.left_join(proj)
		.on(ee.project == proj.name)  # ✅ JOIN PROJECT
		.select(
			ee.name.as_("voucher_no"),
			frappe.qb.terms.ValueWrapper("Expense Entry").as_("transaction_type"),
			ee.posting_date,
			# ❌ OLD → ee.project
			# ✅ NEW → show project_name
			proj.project_name.as_("project"),
			# Party fields
			eei.supplier_name,
			eei.employee_name,
			eei.amount.as_("net_total"),
			eei.vat_amount.as_("tax_amount"),
			eei.vat_percentage.as_("tax_rate"),
			eei.tax_account,
			eei.total_amount.as_("grand_total"),
		)
		.where(ee.docstatus == 1)
		.orderby(ee.posting_date, order=Order.desc)
	)

	# Filters
	if filters.get("from_date"):
		query = query.where(ee.posting_date >= filters.get("from_date"))

	if filters.get("to_date"):
		query = query.where(ee.posting_date <= filters.get("to_date"))

	if filters.get("company"):
		query = query.where(ee.company == filters.get("company"))

	if filters.get("project"):
		query = query.where(ee.project == filters.get("project"))  # keep filter same

	data = query.run(as_dict=True)

	# Party display
	for d in data:
		d["party_display"] = d.get("supplier_name") or d.get("employee_name") or "-"
		d["project"] = d.get("project") or "-"  # safety

	return data


# ═══════════════════════════════════════════════════════════════
# COLUMNS
# ═══════════════════════════════════════════════════════════════


def get_columns():
	return [
		{"label": _("Transaction Type"), "fieldname": "transaction_type", "width": 130},
		{
			"label": _("Voucher No"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "transaction_type",
			"width": 150,
		},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 120,
		},
		# Fixed Party column
		{"label": _("Party"), "fieldname": "party_display", "width": 150},
		{"label": _("Supplier Name"), "fieldname": "supplier_name", "width": 150},
		{"label": _("Employee Name"), "fieldname": "employee_name", "width": 150},
		{"label": _("Net Amount"), "fieldname": "net_total", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Tax Account"),
			"fieldname": "tax_account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 150,
		},
		{"label": _("VAT %"), "fieldname": "tax_rate", "fieldtype": "Float", "width": 80},
		{"label": _("VAT Amount"), "fieldname": "tax_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
	]


# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════


def get_summary(data):
	if not data:
		return []

	total_net = sum(flt(d.get("net_total", 0)) for d in data)
	total_tax = sum(flt(d.get("tax_amount", 0)) for d in data)
	total_grand = sum(flt(d.get("grand_total", 0)) for d in data)

	return [
		{"label": _("Total Expense Amount"), "value": total_net, "datatype": "Currency"},
		{"label": _("Total Expense VAT"), "value": total_tax, "datatype": "Currency"},
		{"label": _("Total Expense with VAT"), "value": total_grand, "datatype": "Currency"},
	]

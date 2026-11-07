# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Division = Cost Center.

Every document carries its division in the standard `cost_center` field, shown
with the label "Division". Using the same fieldname everywhere means ERPNext's
mappers copy it along the flow: Lead -> Quotation -> Sales Order -> Project /
Sales Invoice, and Project -> Project Budget / Manpower Entry / purchasing.

* Documents that already have a header `cost_center` field: relabelled.
* Documents without one: a `cost_center` custom field is added.
* Item / account rows with `cost_center`: relabelled, and filled from the header
  division when left empty or on the company default (see apply_division_to_rows).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

LABEL = "Division"
LINK_FILTERS = '[["Cost Center","is_group","=",0]]'

# doctype: (insert_after when the field has to be added, mandatory)
HEADER_DOCTYPES = {
	"Lead": ("source", 1),
	"Quotation": ("order_type", 1),
	"Sales Order": ("order_type", 0),
	"Delivery Note": ("company", 0),
	"Sales Invoice": ("company", 0),
	"Project": ("company", 0),
	"Material Request": ("material_request_type", 0),
	"Purchase Order": ("company", 0),
	"Purchase Receipt": ("company", 0),
	"Purchase Invoice": ("company", 0),
	"Stock Entry": ("stock_entry_type", 0),
	"Payment Entry": ("company", 0),
	"Expense Claim": ("company", 0),
}

ROW_DOCTYPES = [
	"Sales Order Item",
	"Delivery Note Item",
	"Sales Invoice Item",
	"Material Request Item",
	"Purchase Order Item",
	"Purchase Receipt Item",
	"Purchase Invoice Item",
	"Stock Entry Detail",
	"Journal Entry Account",
	"Payment Entry Deduction",
	"Expense Claim Detail",
]


def _exists(doctype):
	return bool(frappe.db.exists("DocType", doctype))


def _standard_field(doctype):
	"""The doctype's own (non-custom) cost_center field, if any."""
	meta = frappe.get_meta(doctype)
	df = meta.get_field("cost_center")
	if df and not df.get("is_custom_field"):
		return df
	return None


def _label(doctype, fieldname="cost_center"):
	make_property_setter(doctype, fieldname, "label", LABEL, "Data", validate_fields_for_doctype=False)


def setup_division_fields():
	"""Idempotent: relabel or add the Division field on all flow documents."""
	to_create = {}
	for doctype, (insert_after, reqd) in HEADER_DOCTYPES.items():
		if not _exists(doctype):
			continue
		if _standard_field(doctype):
			_label(doctype)
			if reqd:
				make_property_setter(
					doctype, "cost_center", "reqd", 1, "Check", validate_fields_for_doctype=False
				)
		else:
			meta = frappe.get_meta(doctype)
			to_create[doctype] = [
				{
					"fieldname": "cost_center",
					"label": LABEL,
					"fieldtype": "Link",
					"options": "Cost Center",
					"insert_after": insert_after if meta.has_field(insert_after) else None,
					"reqd": reqd,
					"in_standard_filter": 1,
					"in_list_view": 1 if doctype in ("Lead", "Quotation") else 0,
					"link_filters": LINK_FILTERS,
					"description": "Division (Cost Center) this document belongs to",
				}
			]
	if to_create:
		create_custom_fields(to_create, ignore_validate=True, update=True)

	# Division numbering: code per division, shared reference number per enquiry
	numbering_fields = {
		"Cost Center": [
			{
				"fieldname": "custom_division_code",
				"label": "Division Code",
				"fieldtype": "Data",
				"insert_after": "cost_center_name",
				"in_list_view": 1,
				"description": "Short code used in document numbers, e.g. SCF for Scaffolding, CRD for Cradle",
			}
		]
	}
	for doctype in ("Lead", "Quotation", "Sales Order", "Project"):
		if _exists(doctype):
			numbering_fields[doctype] = [
				{
					"fieldname": "custom_division_ref",
					"label": "Division Ref No.",
					"fieldtype": "Data",
					"insert_after": "cost_center",
					"read_only": 1,
					"no_copy": 1,
					"in_standard_filter": 1,
					"search_index": 1,
					"description": "Division, year and sequence shared by the Lead, Quotation, Sales Order and Project of one enquiry",
				}
			]
	create_custom_fields(numbering_fields, ignore_validate=True, update=True)

	for doctype in ROW_DOCTYPES:
		if _exists(doctype) and frappe.get_meta(doctype).has_field("cost_center"):
			_label(doctype)

	frappe.clear_cache()


def remove_division_fields():
	"""For uninstall: drop added fields and label overrides."""
	frappe.db.delete(
		"Custom Field", {"fieldname": "cost_center", "dt": ["in", list(HEADER_DOCTYPES)], "label": LABEL}
	)
	frappe.db.delete("Custom Field", {"fieldname": ["in", ["custom_division_code", "custom_division_ref"]]})
	frappe.db.delete(
		"Property Setter",
		{
			"field_name": "cost_center",
			"property": ["in", ["label", "reqd"]],
			"doc_type": ["in", list(HEADER_DOCTYPES) + ROW_DOCTYPES],
		},
	)


def apply_division_to_rows(doc, method=None):
	"""doc_event (validate): rows without their own division take the header's.

	A row keeps a division that was chosen on purpose; only empty rows and rows on the
	company's default cost center follow the header.
	"""
	division = doc.get("cost_center")
	if not division:
		return
	default = frappe.get_cached_value("Company", doc.company, "cost_center") if doc.get("company") else None
	for table in ("items", "accounts"):
		for row in doc.get(table) or []:
			if not row.meta.has_field("cost_center"):
				continue
			if not row.get("cost_center") or row.get("cost_center") == default:
				row.cost_center = division

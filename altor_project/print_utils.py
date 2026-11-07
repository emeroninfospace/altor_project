# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Helpers for the Altor print formats (registered as Jinja methods in hooks.py).

Company details come from the Company record and its linked records, so they
are maintained on the site, not in the print format code:

* Company: name, logo, TRN (tax_id), phone, email, website
* Company > Print Settings tab fields: Arabic name, accent colour, stamp,
  authorised signature / signatory, footer note
* Address linked to the Company (the document's company address, else the
  default company address)
* Bank Account marked "Is Company Account" (the default one first)
"""

import re

import frappe
from frappe.utils import cstr, flt, strip_html

DEFAULT_ACCENT = "#1f4e8c"


def altor_company(company=None, doc=None):
	"""Everything the print header / footer needs about the company."""
	company = (
		company or (doc.get("company") if doc else None) or frappe.defaults.get_global_default("company")
	)
	if not company:
		return frappe._dict(name="", lines=[], accent=DEFAULT_ACCENT, bank=None)
	c = frappe.get_cached_doc("Company", company)
	info = frappe._dict(
		name=c.company_name or c.name,
		name_ar=c.get("custom_company_name_in_arabic"),
		logo=c.get("company_logo"),
		trn=c.get("tax_id")
		or (doc.get("company_trn") if doc else None)
		or (doc.get("company_tax_id") if doc else None),
		phone=c.get("phone_no"),
		email=c.get("email"),
		website=c.get("website"),
		accent=c.get("custom_print_accent_color") or DEFAULT_ACCENT,
		stamp=c.get("custom_company_stamp"),
		signature=c.get("custom_authorised_signature"),
		signatory=c.get("custom_authorised_signatory"),
		footer_note=c.get("custom_print_footer_note"),
		address=_company_address(company, doc),
		bank=_company_bank(company),
	)
	return info


def _company_address(company, doc=None):
	"""Company address as a list of lines."""
	display = None
	if doc:
		display = doc.get("company_address_display") or doc.get("billing_address_display")
		if not display and doc.get("company_address"):
			display = _address_display(doc.get("company_address"))
	if not display:
		try:
			from erpnext.setup.doctype.company.company import get_default_company_address

			name = get_default_company_address(company)
			display = _address_display(name) if name else None
		except Exception:
			display = None
	return _lines(display)


def _address_display(name):
	try:
		from frappe.contacts.doctype.address.address import get_address_display

		return get_address_display(name)
	except Exception:
		return None


def _company_bank(company):
	if not frappe.db.exists("DocType", "Bank Account"):
		return None
	rows = frappe.get_all(
		"Bank Account",
		filters={"company": company, "is_company_account": 1},
		fields=["name", "account_name", "bank", "bank_account_no", "iban", "branch_code", "is_default"],
		order_by="is_default desc, creation asc",
		limit=1,
	)
	if not rows:
		return None
	bank = rows[0]
	if bank.bank and frappe.db.has_column("Bank", "swift_number"):
		bank.swift = frappe.db.get_value("Bank", bank.bank, "swift_number")
	return bank


def _lines(html_or_text):
	"""Address / multi-line text -> clean list of lines."""
	if not html_or_text:
		return []
	text = re.sub(r"<br\s*/?>", "\n", cstr(html_or_text), flags=re.I)
	text = strip_html(text)
	return [line.strip(" ,") for line in text.split("\n") if line.strip(" ,")]


BULLETS = ("\u2022", "\u25cf", "\u00b7", "-", "*", "\u2013", "\u25aa")


def altor_lines(text):
	"""Description text -> list of bullet lines (leading bullet characters removed)."""
	out = []
	for line in _lines(text):
		while line[:1] in BULLETS:
			line = line[1:].strip()
		if line:
			out.append(line)
	return out


def altor_party(doc):
	"""Customer / supplier block: name, Arabic name, address lines, TRN, contact."""
	if doc.get("supplier"):
		party_type, party = "Supplier", doc.get("supplier")
		name = doc.get("supplier_name") or party
		name_ar = doc.get("supplier_name_in_arabic")
		address = doc.get("address_display")
	else:
		party_type = "Customer" if doc.get("customer") or doc.get("quotation_to") != "Lead" else "Lead"
		party = doc.get("customer") or doc.get("party_name")
		name = doc.get("customer_name") or doc.get("title") or party
		name_ar = doc.get("customer_name_in_arabic")
		address = doc.get("address_display") or doc.get("customer_address_display")
	trn = doc.get("tax_id")
	if party and party_type in ("Customer", "Supplier"):
		values = frappe.db.get_value(party_type, party, ["tax_id"], as_dict=True) or {}
		trn = trn or values.get("tax_id")
		if not name_ar and frappe.db.has_column(party_type, f"{party_type.lower()}_name_in_arabic"):
			name_ar = frappe.db.get_value(party_type, party, f"{party_type.lower()}_name_in_arabic")
	if not address and party:
		address_name = frappe.db.get_value(
			"Dynamic Link",
			{"link_doctype": party_type, "link_name": party, "parenttype": "Address"},
			"parent",
		)
		address = _address_display(address_name) if address_name else None
	return frappe._dict(
		type=party_type,
		name=name,
		name_ar=name_ar,
		address=_lines(address),
		trn=trn,
		contact=doc.get("contact_display") or doc.get("custom_kind_attention"),
		phone=doc.get("contact_mobile") or doc.get("contact_phone"),
		email=doc.get("contact_email"),
	)


def altor_item_taxes(doc):
	"""VAT per item row: {row name: {rate, amount, total}}.

	Uses the UAE regional item fields (tax_rate / tax_amount) when they are filled,
	otherwise splits the document's taxes over the rows by net amount.
	"""
	items = doc.get("items") or []
	net_total = flt(doc.get("net_total")) or sum(flt(i.get("net_amount") or i.get("amount")) for i in items)
	doc_tax = flt(doc.get("total_taxes_and_charges"))
	out = {}
	for item in items:
		net = flt(item.get("net_amount") or item.get("amount"))
		amount = (
			flt(item.get("tax_amount"))
			if item.get("tax_amount")
			else (net / net_total * doc_tax if net_total else 0)
		)
		rate = flt(item.get("tax_rate")) if item.get("tax_rate") else (amount / net * 100 if net else 0)
		out[item.name] = frappe._dict(rate=round(rate, 2), amount=amount, total=net + amount, net=net)
	return out


def altor_item_groups(doc):
	"""Document items grouped by item group (work package).

	Returns [{title, total, items: [{description, lines, uom, qty, rate, amount}]}].
	"""
	return _items_as_groups(doc)


def altor_validity_days(doc):
	from frappe.utils import date_diff

	if doc.get("valid_till") and doc.get("transaction_date"):
		return date_diff(doc.valid_till, doc.transaction_date)
	return None


def _items_as_groups(doc):
	groups, order = {}, []
	for item in doc.get("items") or []:
		key = item.get("item_group") or ""
		if key not in groups:
			order.append(key)
			groups[key] = frappe._dict(title=key, total=0, items=[])
		groups[key]["items"].append(
			frappe._dict(
				description=item.get("description") or item.get("item_name"),
				lines=[item.get("item_name")]
				if not item.get("description")
				else altor_lines(item.get("description")),
				uom=item.get("uom"),
				qty=flt(item.get("qty")),
				rate=flt(item.get("rate")),
				amount=flt(item.get("amount")),
			)
		)
		groups[key]["total"] += flt(item.get("amount"))
	return [groups[k] for k in order]

# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""ALTOR print designs (the client's 2026 templates) for the system's documents.

altor_print_form(doc, kind) builds the page content (sections, rows, tables, terms) and
templates/print/altor_form.html draws it, so every document shares one look:

* Tax Invoice ............. Sales Invoice
* Purchase Order .......... Purchase Order (General / Asset / Cross Hire, page 2 = terms)
* Subcontract Order ....... Subcontract Work Order (Annex A scope, Annex B terms)
* Delivery Note ........... Delivery Note (trading and hire variants) and Asset Allocation
* Return Note ............. Asset Return, Purchase Receipt return (return to supplier)
* Timesheet ............... Timesheet (one sheet per employee on a crew timesheet)
* Payslip ................. Salary Slip (with daily overtime from timesheets)
* Payment Certificate ..... Payment Certificate

The wording of terms and conditions comes from print_content.json (taken from the client's
Excel templates). Company details come from the Company record; the values from the
client's company details sheet are used where the Company has none.
All values are escaped here; the template prints them as they are.
"""

import base64
import json
import os
import re
from functools import lru_cache

import frappe
from frappe.utils import (
	add_days,
	cint,
	cstr,
	date_diff,
	escape_html,
	flt,
	fmt_money,
	formatdate,
	get_datetime,
	getdate,
	money_in_words,
	strip_html,
)

# from the client's "Address & Bank Account details" sheet: used when the Company has no value
DEFAULTS = {
	"name": "Altor Access Equipment and Scaffolding -L.L.C",
	"address": "Office 130, Al Fahim Building, Musaffah M4, Abu Dhabi, U.A.E",
	"po_box": "778087",
	"phone": "+971 2 565 6065",
	"email": "info@altor.ae",
	"website": "www.altor.ae",
	"tagline": "Your Access Needs. Our Expertise.",
	"bank": {
		"account_name": "Altor Access Equipment and Scaffolding -L.L.C",
		"bank": "Emirates NBD Bank (P.J.S.C.)",
		"account_no": "1015989562101",
		"iban": "AE170260001015989562101",
		"swift": "EBILAEAD",
		"currency": "AED",
	},
}

DN_TYPES = (
	"Trading DN",
	"Own Asset - Contract",
	"Own Asset - Hire",
	"Cross Hire - Contract",
	"Cross Hire - Hire",
)
ASSET_TYPES = DN_TYPES[1:]
PO_TYPES = ("General Purchase", "Asset Purchase", "Cross Hire")


def altor_print_form(doc, kind):
	"""Jinja method: the page content of one ALTOR document."""
	builder = BUILDERS.get(kind)
	if not builder:
		frappe.throw(f"Unknown ALTOR print form: {kind}")
	return builder(doc)


# ---------------------------------------------------------------------------
# content, brand, value helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def content():
	with open(frappe.get_app_path("altor_project", "print_content.json"), encoding="utf-8") as f:
		return json.load(f)


@lru_cache(maxsize=8)
def _image(name):
	"""App image as a data URI, so PDFs never depend on fetching it from the site."""
	path = frappe.get_app_path("altor_project", "public", "images", name)
	if not os.path.exists(path):
		return ""
	with open(path, "rb") as f:
		return "data:image/png;base64," + base64.b64encode(f.read()).decode()


@lru_cache(maxsize=1)
def font_css():
	"""Carlito (metric twin of Calibri, the font of the client's templates; SIL OFL) embedded in the
	page, so the PDF has the same letter widths on a server without Calibri. Latin subset only.
	Written as "local(...), url(data:...)" so Frappe's PDF URL rewriting leaves it alone."""
	faces = []
	for weight, style, name in (
		(400, "normal", "regular"),
		(700, "normal", "bold"),
		(400, "italic", "italic"),
	):
		path = frappe.get_app_path("altor_project", "public", "fonts", f"carlito-{name}.ttf")
		if not os.path.exists(path):
			continue
		with open(path, "rb") as f:
			data = base64.b64encode(f.read()).decode()
		faces.append(
			"@font-face { font-family: 'AltorCarlito'; "
			f"src: local('Carlito'), url(data:font/truetype;base64,{data}) format('truetype'); "
			f"font-weight: {weight}; font-style: {style}; }}"
		)
	return "\n".join(faces)


def brand(doc=None):
	"""Company details for the header, footer and bank block."""
	company = (doc.get("company") if doc else None) or frappe.defaults.get_global_default("company")
	c = (
		frappe.get_cached_doc("Company", company)
		if company and frappe.db.exists("Company", company)
		else None
	)
	d = DEFAULTS
	name = d["name"]
	if c and _plain(c.company_name) != _plain(d["name"]):
		name = c.company_name
	address, po_box = _company_address(company, doc)
	phone = (c and c.get("phone_no")) or d["phone"]
	email = (c and c.get("email")) or d["email"]
	website = re.sub(r"^https?://", "", (c and c.get("website")) or d["website"]).rstrip("/")
	po_box = po_box or d["po_box"]
	address = address or d["address"]
	return frappe._dict(
		name=_e(name),
		name_caps=_e(
			name.upper().replace(" AND ", " & ").replace(" -L.L.C", " LLC").replace(" - L.L.C", " LLC")
		),
		address=_e(address),
		address_line=_e(f"{address}  |  P.O. Box {po_box}"),
		contact_line=_e(f"{phone}  |  {email}  |  {website}"),
		contact_line_po=_e(f"P.O. Box {po_box}  |  {phone}  |  {email}  |  {website}"),
		website=_e(website),
		tagline=_e(d["tagline"]),
		trn=_e((c and c.get("tax_id")) or (doc.get("company_trn") if doc else "") or ""),
		logo=(c and c.get("company_logo")) or _image("altor_logo.png"),
		logo_white=_image("altor_logo_white.png"),
		watermark=_image("altor_watermark.png"),
		bank=_bank(company),
	)


def _plain(text):
	return re.sub(r"[^a-z]", "", cstr(text).lower().replace("llc", "").replace("l.l.c", ""))


def _company_address(company, doc=None):
	"""(address line, P.O. box) from the company's address record, if there is one."""
	name = doc.get("company_address") if doc else None
	if not name and company:
		name = frappe.db.get_value(
			"Dynamic Link",
			{"link_doctype": "Company", "link_name": company, "parenttype": "Address"},
			"parent",
		)
	if not name:
		return None, None
	a = frappe.db.get_value(
		"Address",
		name,
		["address_line1", "address_line2", "city", "state", "country", "pincode"],
		as_dict=True,
	)
	if not a:
		return None, None
	country = "U.A.E" if cstr(a.country).lower() in ("united arab emirates", "uae", "u.a.e") else a.country
	parts = [a.address_line1, a.address_line2, a.city, country]
	return ", ".join(p for p in parts if p), a.pincode


def _bank(company):
	d = dict(DEFAULTS["bank"])
	if company and frappe.db.exists("DocType", "Bank Account"):
		rows = frappe.get_all(
			"Bank Account",
			filters={"company": company, "is_company_account": 1},
			fields=["account_name", "bank", "bank_account_no", "iban"],
			order_by="is_default desc, creation asc",
			limit=1,
		)
		if rows:
			r = rows[0]
			swift = (
				frappe.db.get_value("Bank", r.bank, "swift_number")
				if r.bank and frappe.db.has_column("Bank", "swift_number")
				else None
			)
			d.update(
				account_name=r.account_name or d["account_name"],
				bank=r.bank,
				account_no=r.bank_account_no,
				iban=r.iban,
				swift=swift,
			)
	return frappe._dict({k: _e(v) for k, v in d.items()})


def _e(value):
	"""Escaped text for printing; dates formatted, line breaks kept."""
	if value is None or value == "":
		return ""
	if hasattr(value, "strftime") and not hasattr(value, "hour"):
		return formatdate(value)
	text = cstr(value)
	if "<" in text and re.search(r"</?(p|br|div|ul|li|span|b|strong)\b", text, re.I):
		text = strip_html(re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", text, flags=re.I))
	return escape_html(text.strip()).replace("\n", "<br>")


def _d(value):
	return formatdate(value) if value else ""


def _m(value, blank_zero=False):
	if blank_zero and not flt(value):
		return ""
	return fmt_money(flt(value), precision=2)


def _q(value):
	value = flt(value, 3)
	return fmt_money(value, precision=2) if value % 1 else f"{int(value):,}"


def _pct(value):
	value = flt(value, 2)
	return (f"{value:g}" if value % 1 else f"{int(value)}") + "%"


def _join(*values, sep=" / "):
	return sep.join(_e(v) for v in values if v not in (None, ""))


def _unique(values):
	out = []
	for v in values:
		if v and v not in out:
			out.append(v)
	return out


def _user(user):
	return _e(frappe.utils.get_fullname(user)) if user else ""


def _contact(doc):
	return _join(doc.get("contact_display"), doc.get("contact_mobile") or doc.get("contact_phone"))


def _item_desc(item):
	name = _e(item.get("item_name") or item.get("item_code"))
	desc = cstr(item.get("description"))
	plain = strip_html(desc).strip()
	if plain and plain != cstr(item.get("item_name")).strip():
		return f"<b>{name}</b><div class='desc-sub'>{_e(desc)}</div>"
	return name


def _vat(doc):
	from altor_project.print_utils import altor_item_taxes

	return altor_item_taxes(doc)


def _foot_code(code):
	"""Template code line ('ALTOR-PROC-GPO | Rev.01 | www.altor.ae'), escaped. The template's fixed
	"Page 1 of 2" is left out: long documents run to more pages, which the page number shows."""
	code = re.sub(r"\s*Page \d+ of \d+\s*", " ", cstr(code))
	return _e(re.sub(r"\|\s+•", "|", code)).replace("  ", " &nbsp;")


def _form(doc, title, subtitle, pages, header="standard", br=None):
	return frappe._dict(
		fonts=font_css(),
		brand=br or brand(doc),
		title=_e(title),
		subtitle=_e(subtitle),
		header=header,
		pages=pages,
	)


def _sign_block(title, heads, rows, notes=None, row_cls="fill"):
	return {"t": "signs", "title": title, "heads": heads, "rows": rows, "notes": notes, "row_cls": row_cls}


def _status(doc):
	if doc.get("docstatus") == 2:
		return "Cancelled"
	if doc.get("docstatus") == 0:
		return "Draft"
	return _e(doc.get("status") or "Submitted")


# ---------------------------------------------------------------------------
# Tax Invoice (Sales Invoice)
# ---------------------------------------------------------------------------


def tax_invoice(doc):
	from altor_project.print_utils import altor_party

	br_ = brand(doc)
	p = altor_party(doc)
	is_return = cint(doc.get("is_return"))
	vat = _vat(doc)

	refs = _unique([i.get("delivery_note") for i in doc.get("items") or []])
	refs += _unique([t.get("time_sheet") for t in doc.get("timesheets") or []])
	if doc.get("custom_certificate_reference"):
		refs.append(doc.custom_certificate_reference)
	period = doc.get("custom_billing_period")
	if not period and doc.get("from_date") and doc.get("to_date"):
		period = f"{_d(doc.from_date)} - {_d(doc.to_date)}"
	supply = doc.get("custom_date_of_supply")
	if not supply and refs:
		dn_dates = [
			frappe.db.get_value("Delivery Note", n, "posting_date")
			for n in refs
			if frappe.db.exists("Delivery Note", n)
		]
		supply = max(dn_dates) if dn_dates else None

	left = [
		["Customer", _e(p.name)],
		["Address", "<br>".join(_e(x) for x in p.address)],
		["TRN", _e(p.trn)],
		["Attention", _e(p.contact)],
		["Email / Tel.", _join(p.email, p.phone)],
		["Project / Site", _join(doc.get("project"), doc.get("custom_location"))],
		["Division", _e(doc.get("cost_center"))],
	]
	right = [
		["Credit Note No." if is_return else "Invoice No.", _e(doc.name)],
		["Credit note date" if is_return else "Invoice date", _d(doc.posting_date)],
		["Date of supply", _d(supply or doc.posting_date)],
		["Client PO / Contract", _join(doc.get("po_no"), doc.get("custom_contract_reference"))],
		["DN / PC / Timesheet", _join(*refs, sep=", ")],
		["Billing period", _e(period)],
		["Payment terms", _e(doc.get("payment_terms_template"))],
		[
			"Against invoice" if is_return else "Due date",
			_e(doc.get("return_against")) if is_return else _d(doc.get("due_date")),
		],
	]

	rows, gross_total, discount_total = [], 0, 0
	for idx, item in enumerate(doc.get("items") or [], 1):
		t = vat[item.name]
		unit = (
			flt(item.get("price_list_rate"))
			if flt(item.get("price_list_rate")) > flt(item.rate)
			else flt(item.rate)
		)
		line_gross = flt(unit * flt(item.qty), 2)
		discount = flt(line_gross - t.net, 2)
		if abs(discount) < 0.005:
			discount, line_gross = 0, t.net
		gross_total += line_gross
		discount_total += discount
		rows.append(
			{
				"cells": [
					idx,
					_e(item.item_code),
					_item_desc(item),
					_q(item.qty),
					_e(item.uom),
					_m(unit),
					_m(discount, True),
					_m(t.net),
					_pct(t.rate),
					_m(t.amount),
					_m(t.total),
				]
			}
		)

	grand = flt(doc.get("rounded_total") or doc.get("grand_total"))
	paid = grand - flt(doc.get("outstanding_amount")) if doc.docstatus == 1 and not is_return else 0
	balance = flt(doc.get("outstanding_amount")) if doc.docstatus == 1 else grand
	cur = _e(doc.get("currency") or "AED")
	b = br_.bank
	totals = [
		["Subtotal before discount", _m(gross_total)],
		["Discount", _m(discount_total)],
		["Net amount excl. VAT", _m(doc.get("net_total"))],
		["VAT amount", _m(doc.get("total_taxes_and_charges"))],
	]
	if flt(doc.get("rounding_adjustment")):
		totals.append(["Rounding adjustment", _m(doc.rounding_adjustment)])
	totals += [
		[f"TOTAL INCL. VAT ({cur})", _m(grand), "gold"],
		["Payments already received", _m(paid, True), "small"],
		["BALANCE PAYABLE", _m(balance), "navy"],
	]
	in_words = doc.get("in_words") or money_in_words(abs(grand), doc.get("currency"))
	inv = content()["invoice"]
	blocks = [
		{
			"t": "grid",
			"title": "BILL TO",
			"title_right": "CREDIT NOTE DETAILS" if is_return else "INVOICE DETAILS",
			"left": left,
			"right": right,
		},
		{
			"t": "items",
			"title": f"SUPPLY DETAILS  /  ALL AMOUNTS IN {cur}",
			"cols": [
				["No.", 4, "c"],
				["Item / code", 10, ""],
				["Description of goods / services", 26, ""],
				["Qty", 6, "r"],
				["UOM", 6, ""],
				["Unit rate", 9, "r"],
				["Discount", 8, "r"],
				["Net value", 9, "r"],
				["VAT %", 5, "c"],
				["VAT amount", 8, "r"],
				["Gross amount", 9, "r"],
			],
			"rows": rows,
			"fill": [7, 9, 10],
		},
		{
			"t": "totals",
			"left_title": "PAYMENT / BANK DETAILS",
			"left": [
				f"Beneficiary: {b.account_name}",
				f"Bank: {b.bank}",
				f"Account No.: {b.account_no}",
				f"IBAN: {b.iban}",
				f"SWIFT: {b.swift}  |  Currency: {b.currency}" if b.swift else f"Currency: {b.currency}",
				f"<i class='mu'>{_e(inv['remit_note'])}</i>",
			],
			"rows": totals,
			"left_width": 56,
		},
		{
			"t": "words",
			"rows": [
				["Amount in words", _e(in_words)],
				[
					"Notes / tax treatment",
					_e(doc.get("custom_tax_note") or strip_html(cstr(doc.get("terms")))),
				],
			],
		},
		_sign_block(
			"",
			[],
			[
				[
					f"For ALTOR &nbsp;|&nbsp; Authorized signatory: {_e(frappe.utils.get_fullname(doc.owner)) if doc.docstatus == 1 else '__________________'}",
					"",
					f"<i>{_e(inv['thanks'])}</i>",
				]
			],
			row_cls="",
		),
	]
	page = {"blocks": blocks, "trn_row": ["ALTOR TRN", br_.trn]}
	return _form(
		doc,
		"TAX CREDIT NOTE" if is_return else "TAX INVOICE",
		f"{doc.get('currency') or 'AED'}  /  UAE",
		[page],
		br=br_,
	)


# ---------------------------------------------------------------------------
# Purchase Order
# ---------------------------------------------------------------------------

PO_FIELDS = {
	"Delivery location": "custom_delivery_location",
	"Delivery / hire location": "custom_delivery_location",
	"Delivery / mobilization date": "schedule_date",
	"Delivery date": "schedule_date",
	"Delivery / transport terms": "custom_delivery_terms",
	"Delivery schedule": "custom_delivery_schedule",
	"Warranty / service period": "custom_warranty_period",
	"Warranty duration / start event": "custom_warranty_period",
	"Scope / exclusions": "custom_scope_exclusions",
	"Delivery note requirements": "custom_dn_requirements",
	"Partial delivery permitted?": "custom_partial_delivery",
	"Site contact / phone": "custom_site_contact",
	"Payment terms": "payment_terms_template",
	"Currency": "currency",
	"Required documents": "custom_required_documents",
	"Required certificates / manuals": "custom_required_documents",
	"Acceptance criteria": "custom_acceptance_criteria",
	"Delivery / acceptance milestones": "custom_acceptance_criteria",
	"Special conditions / attachment": "custom_special_conditions",
	"Invoice submission email": "custom_invoice_email",
	"Additional instructions": "custom_delivery_instructions",
	"Asset condition (new / used)": "custom_asset_condition",
	"Testing / commissioning": "custom_testing_commissioning",
	"Training / spares / support": "custom_training_support",
	"Payment milestones / attachment": "custom_payment_milestones",
	"Asset class / specification ref.": "custom_asset_spec_ref",
	"Inspection location": "custom_inspection_location",
	"Warranty response time": "custom_warranty_response",
	"Minimum hire / off-hire notice": "custom_min_hire",
	"Collection / return party": "custom_collection_party",
	"Proration / billing cycle": "custom_billing_cycle",
	"Mobilization / demobilization": "custom_mobilization",
	"Breakdown replacement time": "custom_breakdown_time",
	"Operator / fuel / maintenance": "custom_operator_fuel",
	"Loading / unloading / installation": "custom_loading",
	"Loss / damage rate schedule": "custom_loss_damage_rates",
	"Permitted sites / insurance scope": "custom_permitted_sites",
	"Hire type / restrictions": "custom_hire_type",
}


def _po_value(doc, label):
	if label == "Est. hire from / to":
		return _join(_d(doc.get("custom_hire_from")), _d(doc.get("custom_hire_to")), sep=" to ")
	field = PO_FIELDS.get(label)
	value = doc.get(field) if field else None
	if label in ("Delivery location", "Delivery / hire location") and not value:
		value = doc.get("shipping_address_display") or doc.get("custom_note")
	if label == "Delivery / transport terms" and not value and doc.get("incoterm"):
		value = " ".join(x for x in (doc.incoterm, doc.get("named_place")) if x)
	if label == "Payment terms" and not value and doc.get("payment_schedule"):
		value = ", ".join(
			_unique([r.get("description") or r.get("payment_term") for r in doc.payment_schedule])
		)
	return _d(value) if field == "schedule_date" else _e(value)


def purchase_order(doc):
	po_type = doc.get("custom_po_type") if doc.get("custom_po_type") in PO_TYPES else "General Purchase"
	cfg = content()["po"][po_type]
	br_ = brand(doc)
	from altor_project.print_utils import altor_party

	p = altor_party(doc)
	vat = _vat(doc)
	items = doc.get("items") or []
	pr = doc.get("custom_pr_reference") or ", ".join(_unique([i.get("material_request") for i in items]))
	quote = doc.get("custom_supplier_quote_ref") or ", ".join(
		_unique([i.get("supplier_quotation") for i in items])
	)
	left = [
		["PO number", f"<b>{_e(doc.name)}</b>"],
		["PO date", _d(doc.transaction_date)],
		["Revision", _e(doc.get("custom_revision") or "00")],
		["ALTOR TRN", br_.trn],
		["PR / enquiry reference", _e(pr)],
		["Supplier quote ref. / date", _e(quote)],
	]
	right = [
		["Supplier / vendor name", f"<b>{_e(p.name)}</b>"],
		["Supplier address", "<br>".join(_e(x) for x in p.address)],
		["Supplier TRN", _e(p.trn)],
		["Supplier contact / phone", _join(p.contact, p.phone)],
		["Supplier email", _e(p.email)],
		["Project / cost centre", _join(doc.get("project"), doc.get("cost_center"))],
	]
	comm_left = [[_e(a), _po_value(doc, a)] for a, b in cfg["commercial"]]
	comm_right = [[_e(b), _po_value(doc, b)] for a, b in cfg["commercial"]]

	hire = po_type == "Cross Hire"
	rows = []
	for idx, item in enumerate(items, 1):
		t = vat[item.name]
		if hire:
			basis = item.get("custom_hire_basis") or ""
			periods = flt(item.get("custom_hire_periods"))
			units = flt(item.qty) / periods if periods and basis != "One-off" else flt(item.qty)
			cells = [
				idx,
				_e(item.item_code),
				_item_desc(item),
				_q(units),
				_e(item.uom),
				_e(basis),
				_q(periods) if periods and basis != "One-off" else "",
				_m(item.rate),
				_pct(t.rate),
				_m(t.net),
				_m(t.amount),
			]
		else:
			plr = flt(item.get("price_list_rate"))
			disc = flt(item.get("discount_percentage")) or (
				(1 - flt(item.rate) / plr) * 100 if plr > flt(item.rate) else 0
			)
			cells = [
				idx,
				_e(item.item_code),
				_item_desc(item),
				_q(item.qty),
				_e(item.uom),
				_m(plr if disc else item.rate),
				_pct(disc) if disc else "",
				_e(item.get("custom_make_reference")),
				_pct(t.rate),
				_m(t.net),
				_m(t.amount),
			]
		rows.append({"cells": cells})
	if hire:
		cols = [
			["#", 3, "c"],
			["Item code", 9, ""],
			["Description / specification", 25, ""],
			["Qty", 6, "r"],
			["UOM", 6, ""],
			["Hire basis", 8, ""],
			["Est. periods", 7, "r"],
			["Unit rate", 9, "r"],
			["VAT %", 5, "c"],
			["Net amount", 11, "r"],
			["VAT amount", 10, "r"],
		]
	else:
		cols = [
			["#", 3, "c"],
			["Item code", 9, ""],
			["Description / specification", 25, ""],
			["Qty", 6, "r"],
			["UOM", 6, ""],
			["Unit price", 9, "r"],
			["Disc. %", 6, "r"],
			["Reference / make", 10, ""],
			["VAT %", 5, "c"],
			["Net amount", 10, "r"],
			["VAT amount", 9, "r"],
		]
	totals = [["Subtotal", _m(doc.get("total"))]]
	if flt(doc.get("discount_amount")):
		totals.append(["Discount", _m(-flt(doc.discount_amount))])
	totals.append(["VAT", _m(doc.get("total_taxes_and_charges"))])
	totals.append(
		[
			f"TOTAL incl. VAT ({_e(doc.currency)})",
			_m(doc.get("rounded_total") or doc.get("grand_total")),
			"navy",
		]
	)
	in_words = doc.get("in_words") or money_in_words(flt(doc.get("grand_total")), doc.get("currency"))
	accept_text = [_e(cfg["acceptance"])]
	if doc.get("terms"):
		accept_text.append("<b>Special terms:</b> " + _e(doc.terms))
	signer = _user(doc.owner)
	page1 = {
		"blocks": [
			{"t": "grid", "title": "01  /  ORDER & SUPPLIER DETAILS", "left": left, "right": right},
			{
				"t": "grid",
				"title": "02  /  COMMERCIAL & DELIVERY INSTRUCTIONS",
				"left": comm_left,
				"right": comm_right,
			},
			{
				"t": "items",
				"title": "03  /  ORDER LINE ITEMS  &bull;  ALL RATES EXCLUDING VAT",
				"cols": cols,
				"rows": rows,
				"fill": [9, 10],
			},
			{
				"t": "totals",
				"left": [f"<i class='mu'>{_e(n)}</i>" for n in cfg["line_notes"]]
				+ [f"<b>Amount in words:</b> {_e(in_words)}"],
				"rows": totals,
				"left_width": 60,
			},
			{"t": "text", "title": "04  /  AUTHORIZATION & ACCEPTANCE", "lines": accept_text},
			_sign_block(
				"",
				["Prepared by", "Authorized by ALTOR", "Supplier acceptance / stamp"],
				[
					[
						f"Name / signature / date: {signer}",
						"Name / signature / date:",
						"Name / signature / date:",
					]
				],
				row_cls="fill tall",
			),
		],
		"foot": [_foot_code(cfg["code"])],
	}
	page2 = {
		"title": "TERMS &amp; CONDITIONS",
		"blocks": [
			{
				"t": "grid",
				"title": "APPENDIX A  /  PURCHASE ORDER CONDITIONS",
				"left": [["PO number", _e(doc.name)]],
				"right": [["Supplier", _e(p.name)]],
			},
			{
				"t": "terms",
				"intro": _e(cfg["terms_intro"]),
				"entries": [[f"{i:02d}", _e(t[0]), _e(t[1])] for i, t in enumerate(cfg["terms"], 1)],
				"ack": _e(cfg["terms_ack"]),
			},
		],
		"foot": [_foot_code(cfg["terms_code"])],
	}
	return _form(doc, "PURCHASE ORDER", cfg["subtitle"], [page1, page2], br=br_)


# ---------------------------------------------------------------------------
# Delivery notes and return notes
# ---------------------------------------------------------------------------


def _note_form(doc, kind, variant, values, items, serial_values=None, remarks="", signers=None, title=None):
	"""Delivery note / return note page from the variant's labels and a label -> value map."""
	cfg = content()[kind][variant]
	section1 = cfg.get("section1") or (
		"01  /  DELIVERY & CUSTOMER DETAILS" if kind == "dn" else "01  /  RETURN & PROJECT DETAILS"
	)
	left = [[_e(a), values.get(a, "")] for a, b in cfg["rows"]]
	right = [[_e(b), values.get(b, "")] for a, b in cfg["rows"]]
	rows = [{"cells": [i, *cells]} for i, cells in enumerate(items, 1)]
	signers = signers or ["", "", ""]
	is_dn = kind == "dn"
	blocks = [
		{"t": "grid", "title": _e(section1), "left": left, "right": right},
		{
			"t": "items",
			"title": "02  /  MATERIALS &amp; EQUIPMENT " + ("DELIVERED" if is_dn else "RETURNED"),
			"cols": [
				["No.", 4, "c"],
				["Item code", 11, ""],
				["Description / specification", 28, ""],
				[_e(cfg["serial_label"]), 15, ""],
				["UOM", 7, ""],
				["Qty", 10, "c"],
				["Remarks / condition", 25, ""],
			],
			"rows": rows,
			"pad": max(0, 8 - len(rows)),
			"fill": [5, 6],
			"note": _e(cfg["qty_note"]),
		},
		{
			"t": "text",
			"title": "03  /  " + ("DELIVERY" if is_dn else "RETURN") + " CONDITIONS &amp; REMARKS",
			"lines": [_e(x) for x in cfg["conditions"]],
			"numbered": True,
			"kv": [[("Delivery" if is_dn else "Return") + " / exception remarks", remarks]],
			"wide": True,
		},
		_sign_block(
			"04  /  " + ("DISPATCH" if is_dn else "RETURN") + " &amp; RECEIPT ACKNOWLEDGMENT",
			[_e(h) for h in cfg["sign"]],
			[
				[f"Name: {signers[0]}", f"Name: {signers[1]}", f"Name: {signers[2]}"],
				["Signature:", "Signature:", "Signature:"],
				["Date / time:", "Date / time:", "Date / time:"],
			],
			notes=[_e(cfg["sign_note"]), "", _e("Company stamp (if applicable)")],
			row_cls="",
		),
	]
	page = {"blocks": blocks, "foot": [_foot_code(cfg["code"]), _e(cfg["copies"])]}
	return _form(doc, title or ("DELIVERY NOTE" if is_dn else "RETURN NOTE"), cfg["subtitle"], [page])


def _serial(item):
	bits = [item.get("batch_no"), item.get("serial_no")]
	if not any(bits) and item.get("serial_and_batch_bundle"):
		entries = frappe.get_all(
			"Serial and Batch Entry",
			filters={"parent": item.serial_and_batch_bundle},
			fields=["serial_no", "batch_no"],
			limit=20,
		)
		bits = _unique([e.serial_no or e.batch_no for e in entries])
	return _join(*bits, sep=", ")


def delivery_note(doc):
	variant = doc.get("custom_dn_type") if doc.get("custom_dn_type") in DN_TYPES else "Trading DN"
	if cint(doc.get("is_return")):
		return _customer_return(doc)
	items = doc.get("items") or []
	warehouses = _unique([doc.get("set_warehouse")] + [i.get("warehouse") for i in items])
	values = {
		"Customer / company": f"<b>{_e(doc.customer_name)}</b>",
		"Delivery address / site": _e(doc.get("shipping_address") or doc.get("address_display")),
		"Project / job reference": _e(doc.get("project")),
		"Site contact / phone": _e(doc.get("custom_site_contact")) or _contact(doc),
		"Division": _e(doc.get("cost_center")),
		"Requested by / attention": _e(doc.get("contact_display")),
		"Vehicle / driver": _join(
			doc.get("vehicle_no"), doc.get("driver_name") or doc.get("transporter_name")
		),
		"Customer delivery schedule": _e(doc.get("custom_delivery_schedule")),
		"Packing / shipment ref.": _e(doc.get("custom_packing_ref")),
		"Work package / area": _e(doc.get("custom_work_package")),
		"Expected return / review date": _d(doc.get("custom_expected_return_date")),
		"Agreed on-hire date (if known)": _d(doc.get("custom_on_hire_date")),
		"Hire agreement / schedule": _e(doc.get("custom_hire_agreement")),
		"Delivery note no.": f"<b>{_e(doc.name)}</b>",
		"Dispatch date": _d(doc.posting_date),
		"Client PO / contract": _join(doc.get("po_no"), _d(doc.get("po_date"))),
		"Sales order / job order": _join(*_unique([i.get("against_sales_order") for i in items]), sep=", "),
		"Dispatch from / warehouse": _join(*warehouses, sep=", "),
		"Dispatch location": _join(*warehouses, sep=", "),
		"Issue reference": _e(doc.get("custom_issue_reference")),
		"Delivery time / trip ref.": _join(cstr(doc.get("posting_time"))[:5], doc.get("lr_no")),
		"Delivery status": _e(doc.get("custom_delivery_status")),
		"Related previous DN": _e(doc.get("custom_related_dn")),
		"Mobilisation reference": _e(doc.get("custom_mobilisation_ref")),
		"Hire start basis": _e(doc.get("custom_hire_start_basis")),
	}
	rows = [
		[_e(i.item_code), _item_desc(i), _serial(i), _e(i.uom), _q(i.qty), _e(i.get("custom_remarks"))]
		for i in items
	]
	return _note_form(
		doc,
		"dn",
		variant,
		values,
		rows,
		remarks=_e(doc.get("instructions")),
		signers=[_user(doc.owner), _e(doc.get("driver_name")), ""],
	)


def _customer_return(doc):
	"""Delivery Note return (goods back from the customer): the return note layout."""
	items = doc.get("items") or []
	values = {
		"Customer / company": f"<b>{_e(doc.customer_name)}</b>",
		"Return from / project site": _e(doc.get("shipping_address_display") or doc.get("address_display")),
		"Project / job reference": _e(doc.get("project")),
		"Site contact / phone": _contact(doc),
		"Division": _e(doc.get("cost_center")),
		"Returned by / attention": _e(doc.get("contact_display")),
		"Vehicle / driver": _join(doc.get("vehicle_no"), doc.get("driver_name")),
		"Return reason": _e(doc.get("instructions")),
		"Return note no.": f"<b>{_e(doc.name)}</b>",
		"Return dispatch date": _d(doc.posting_date),
		"Client PO / contract": _e(doc.get("po_no")),
		"Original delivery note(s)": _e(doc.get("return_against")),
		"Return to / warehouse": _join(
			*_unique([doc.get("set_warehouse")] + [i.get("warehouse") for i in items]), sep=", "
		),
		"Return status": _status(doc),
	}
	rows = [[_e(i.item_code), _item_desc(i), _serial(i), _e(i.uom), _q(abs(flt(i.qty))), ""] for i in items]
	return _note_form(
		doc,
		"rn",
		"Own Asset - Contract",
		values,
		rows,
		signers=["", _e(doc.get("driver_name")), _user(doc.owner)],
	)


def _project_info(project):
	if not project:
		return frappe._dict()
	fields = ["customer", "project_name", "sales_order", "cost_center"]
	for f in ("lpo_ref", "lpo_date", "location"):
		if frappe.db.has_column("Project", f):
			fields.append(f)
	return frappe.db.get_value("Project", project, fields, as_dict=True) or frappe._dict()


def _customer_name(customer):
	return frappe.db.get_value("Customer", customer, "customer_name") if customer else None


def asset_allocation(doc):
	variant = doc.get("delivery_type") if doc.get("delivery_type") in ASSET_TYPES else "Own Asset - Contract"
	pr = _project_info(doc.project)
	values = {
		"Customer / company": f"<b>{_e(_customer_name(pr.customer) or pr.customer)}</b>",
		"Delivery address / site": _e(doc.get("site_location") or pr.get("location")),
		"Project / job reference": _join(doc.project, doc.get("project_name")),
		"Site contact / phone": _e(doc.get("site_contact")),
		"Division": _e(doc.get("cost_center")),
		"Requested by / attention": _e(doc.get("requested_by")),
		"Vehicle / driver": _e(doc.get("vehicle_driver")),
		"Work package / area": _e(doc.get("work_package")),
		"Expected return / review date": _d(doc.get("expected_return_date")),
		"Agreed on-hire date (if known)": _d(doc.get("on_hire_date")),
		"Hire agreement / schedule": _e(doc.get("hire_agreement")),
		"Delivery note no.": f"<b>{_e(doc.name)}</b>",
		"Dispatch date": _d(doc.get("delivery_date")),
		"Client PO / contract": _join(pr.get("lpo_ref"), _d(pr.get("lpo_date"))),
		"Sales order / job order": _e(pr.get("sales_order")),
		"Dispatch from / warehouse": _e(doc.get("dispatch_from")),
		"Dispatch location": _e(doc.get("dispatch_from")),
		"Issue reference": _e(doc.get("delivery_ref")),
		"Delivery time / trip ref.": _e(doc.get("trip_ref")),
		"Delivery status": _status(doc),
		"Mobilisation reference": _e(doc.get("mobilisation_ref")),
		"Hire start basis": _e(doc.get("hire_start_basis")),
	}
	rows = [
		[
			_e(i.get("item_code")),
			_e(i.get("asset_name")),
			_e(i.project_asset),
			_e(i.get("uom")),
			_q(i.qty),
			"",
		]
		for i in doc.get("items") or []
	]
	return _note_form(
		doc,
		"dn",
		variant,
		values,
		rows,
		remarks=_e(doc.get("remarks")),
		signers=[_user(doc.owner), _e(doc.get("vehicle_driver")), ""],
	)


def asset_return(doc):
	variant = doc.get("return_type") if doc.get("return_type") in ASSET_TYPES else "Own Asset - Contract"
	pr = _project_info(doc.project)
	allocation_ref = (
		frappe.db.get_value("Asset Allocation", doc.asset_allocation, "delivery_ref")
		if doc.get("asset_allocation")
		else None
	)
	values = {
		"Customer / company": f"<b>{_e(_customer_name(pr.customer) or pr.customer)}</b>",
		"Return from / project site": _e(pr.get("location")),
		"Project / job reference": _join(doc.project, doc.get("project_name")),
		"Site contact / phone": _e(doc.get("site_contact")),
		"Division": _e(doc.get("cost_center")),
		"Returned by / attention": _e(doc.get("returned_by")),
		"Vehicle / driver": _e(doc.get("vehicle_driver")),
		"Work package / area": _e(doc.get("work_package")),
		"Return reason": _e(doc.get("return_reason")),
		"Hire agreement / schedule": _e(doc.get("hire_agreement")),
		"Customer off-hire notice ref.": _e(doc.get("off_hire_notice_ref")),
		"Return note no.": f"<b>{_e(doc.name)}</b>",
		"Return dispatch date": _d(doc.get("return_date")),
		"Client PO / contract": _join(pr.get("lpo_ref"), _d(pr.get("lpo_date"))),
		"Original delivery note(s)": _join(doc.get("asset_allocation"), allocation_ref),
		"Return to / warehouse": _e(doc.get("return_to")),
		"Return authorization ref.": _e(doc.get("return_ref")),
		"Trip / collection ref.": _e(doc.get("trip_ref")),
		"Return status": _status(doc),
		"Inspection / receipt ref.": _e(doc.get("inspection_ref")),
		"Agreed off-hire date / time": _d(doc.get("off_hire_date")),
	}
	rows = []
	for i in doc.get("items") or []:
		notes = []
		if flt(i.get("damaged_qty")):
			notes.append(f"Damaged: {_q(i.damaged_qty)}")
		if i.get("damage_remarks"):
			notes.append(_e(i.damage_remarks))
		rows.append(
			[
				_e(i.get("item_code")),
				_e(i.get("asset_name")),
				_e(i.project_asset),
				_e(i.get("uom")),
				_q(i.returned_qty),
				"<br>".join(notes),
			]
		)
	return _note_form(
		doc,
		"rn",
		variant,
		values,
		rows,
		remarks=_e(doc.get("remarks")),
		signers=[_e(doc.get("returned_by")), _e(doc.get("vehicle_driver")), _user(doc.owner)],
	)


def supplier_return(doc):
	"""Purchase Receipt return: goods (e.g. cross-hire items) sent back to the supplier."""
	from altor_project.print_utils import altor_party

	p = altor_party(doc)
	items = doc.get("items") or []
	original = doc.get("return_against")
	supplier_dn = (
		frappe.db.get_value("Purchase Receipt", original, "supplier_delivery_note") if original else None
	)
	values = {
		"Supplier / company": f"<b>{_e(p.name)}</b>",
		"Supplier return location": "<br>".join(_e(x) for x in p.address),
		"Dispatch from / ALTOR yard": _join(
			*_unique([doc.get("set_warehouse")] + [i.get("warehouse") for i in items]), sep=", "
		),
		"Supplier contact / phone": _join(p.contact, p.phone),
		"Division": _e(doc.get("cost_center")),
		"Returned by / attention": _user(doc.owner),
		"Vehicle / driver": _join(doc.get("lr_no"), doc.get("transporter_name")),
		"Return reason": _e(doc.get("instructions") or doc.get("remarks")),
		"Return note no.": f"<b>{_e(doc.name)}</b>",
		"Return dispatch date": _d(doc.posting_date),
		"Supplier PO / hire agreement": _join(*_unique([i.get("purchase_order") for i in items]), sep=", "),
		"Supplier DN / inward GRN": _join(supplier_dn, original),
		"Return status": _status(doc),
		"Trip / collection ref.": _e(doc.get("lr_no")),
	}
	rows = [[_e(i.item_code), _item_desc(i), _serial(i), _e(i.uom), _q(abs(flt(i.qty))), ""] for i in items]
	form = _note_form(
		doc,
		"rn",
		"Return to Supplier",
		values,
		rows,
		signers=[_user(doc.owner), _e(doc.get("transporter_name")), ""],
	)
	if not cint(doc.get("is_return")):
		form.subtitle = "SUPPLIER RETURN (DRAFT - NOT A RETURN ENTRY)"
	return form


# ---------------------------------------------------------------------------
# Subcontract Order (Subcontract Work Order)
# ---------------------------------------------------------------------------


def subcontract_order(doc):
	cfg = content()["sco"]
	from altor_project.print_utils import altor_party

	supplier = frappe._dict(
		supplier=doc.supplier, supplier_name=frappe.db.get_value("Supplier", doc.supplier, "supplier_name")
	)
	p = altor_party(supplier)
	net = sum(flt(i.amount) for i in doc.get("items") or [])
	tax = flt(doc.get("total_taxes_and_charges"))
	rate = (tax / net * 100) if net else 0
	pr = _project_info(doc.project)
	left = [
		["SCO number", f"<b>{_e(doc.name)}</b>"],
		["Subcontractor", f"<b>{_e(p.name)}</b>"],
		["Address / TRN", "<br>".join([_e(x) for x in p.address] + ([f"TRN: {_e(p.trn)}"] if p.trn else []))],
		["Contact / email", _join(doc.get("subcontractor_contact"), p.email)],
		["Project / code", _join(doc.project, pr.get("project_name"))],
		["ALTOR contact", _e(doc.get("altor_contact"))],
	]
	right = [
		["Issue date", _d(doc.transaction_date)],
		["Revision", _e(doc.get("revision") or "00")],
		["PR / RFQ ref.", _e(doc.get("pr_rfq_ref"))],
		["Quotation ref.", _e(doc.get("quotation_ref"))],
		["Site location", _e(doc.get("site_location") or pr.get("location"))],
		["Site contact", _e(doc.get("site_contact"))],
	]
	cur = frappe.db.get_value("Company", doc.company, "default_currency") if doc.get("company") else "AED"
	c_left = [
		["Pricing basis", _e(doc.get("pricing_basis"))],
		["Start date", _d(doc.get("start_date"))],
		["Payment terms", _e(doc.get("payment_terms"))],
		["Retention %", _pct(doc.retention_percent) if flt(doc.get("retention_percent")) else ""],
		["Defects period", _e(doc.get("defects_period"))],
		["Security / bond", _e(doc.get("security_bond"))],
	]
	c_right = [
		["Currency", _e(cur)],
		["Completion date", _d(doc.get("end_date"))],
		["Billing frequency", _e(doc.get("billing_frequency"))],
		["Advance %", _pct(doc.advance_percent) if flt(doc.get("advance_percent")) else ""],
		["Delay damages", _e(doc.get("delay_damages"))],
		["Insurance limits", _e(doc.get("insurance_limits"))],
	]
	rows = []
	for idx, i in enumerate(doc.get("items") or [], 1):
		desc = _e(i.get("item_name") or i.item_code)
		if (
			i.get("description")
			and strip_html(cstr(i.description)).strip() != cstr(i.get("item_name")).strip()
		):
			desc = f"<b>{desc}</b><div class='desc-sub'>{_e(i.description)}</div>"
		rows.append(
			{"cells": [idx, desc, _e(i.get("uom")), _q(i.quantity), _m(i.rate), _pct(rate), _m(i.amount)]}
		)
	docs_text = [_e(cfg["documents"])]
	if doc.get("special_conditions"):
		docs_text.append(_e(doc.special_conditions))
	page1 = {
		"blocks": [
			{
				"t": "grid",
				"title": "01 &nbsp; ORDER &amp; SUBCONTRACTOR DETAILS",
				"left": left,
				"right": right,
			},
			{
				"t": "grid",
				"title": "02 &nbsp; COMMERCIAL &amp; PROGRAMME DETAILS",
				"left": c_left,
				"right": c_right,
			},
			{
				"t": "items",
				"title": "03 &nbsp; SCHEDULE OF WORKS / RATES",
				"cols": [
					["No.", 5, "c"],
					["Description / scope reference", 45, ""],
					["UOM", 8, ""],
					["Qty", 8, "r"],
					["Unit rate", 11, "r"],
					["VAT %", 7, "c"],
					["Net amount", 16, "r"],
				],
				"rows": rows,
				"fill": [6],
			},
			{
				"t": "totals",
				"left": [f"<i class='mu'>{_e(cfg['order_note'])}</i>"],
				"rows": [
					["Subtotal excl. VAT", _m(net)],
					["VAT amount", _m(tax)],
					["Total order value", _m(net + tax), "navy"],
				],
				"left_width": 55,
			},
			{"t": "text", "title": "04 &nbsp; ORDER DOCUMENTS &amp; ACCEPTANCE", "lines": docs_text},
			_sign_block(
				"",
				["Prepared / checked by", "Authorized by ALTOR", "Subcontractor acceptance"],
				[
					[
						f"Name / signature / date: {_user(doc.owner)}",
						"Name / signature / date",
						"Name / signature / date",
					]
				],
				row_cls="fill tall",
			),
		],
		"foot": [_foot_code(cfg["code"])],
	}
	ref = [["SCO number", _e(doc.name)]], [["Project", _join(doc.project, pr.get("project_name"))]]
	scope_values = [
		doc.get("scope_details"),
		doc.get("exclusions"),
		doc.get("drawings_specs"),
		doc.get("milestones"),
	]
	matrix = [
		{"cells": [_e(r.activity), _e(r.responsible_party), _e(r.clarifications)]}
		for r in doc.get("responsibilities") or []
	] or [{"cells": [_e(a), "", ""]} for a in cfg["matrix"]]
	page2 = {
		"title": "SCOPE &amp; RESPONSIBILITIES",
		"subtitle": _e(cfg["annex_a_subtitle"]),
		"blocks": [
			{
				"t": "grid",
				"title": "01 &nbsp; ORDER REFERENCE &amp; WORK DESCRIPTION",
				"left": ref[0],
				"right": ref[1],
			},
			{
				"t": "words",
				"rows": [
					[_e(label), _e(v)] for label, v in zip(cfg["annex_a_fields"], scope_values, strict=True)
				],
			},
			{
				"t": "items",
				"title": "02 &nbsp; RESPONSIBILITY MATRIX &nbsp;|&nbsp; Complete before issuing",
				"cols": [
					["Activity / resource", 38, ""],
					["Responsible party", 20, ""],
					["Clarifications / requirements", 42, ""],
				],
				"rows": matrix,
				"fill": [1, 2],
				"note": _e(cfg["matrix_note"]),
			},
		],
		"foot": [_foot_code(cfg["annex_a_code"])],
	}
	page3 = {
		"title": "TERMS &amp; CONDITIONS",
		"subtitle": _e(cfg["annex_b_subtitle"]),
		"blocks": [
			{"t": "grid", "title": "", "left": ref[0], "right": ref[1]},
			{
				"t": "terms",
				"title": _e(cfg["terms_title"]),
				"entries": [[f"{i:02d}", _e(t[0]), _e(t[1])] for i, t in enumerate(cfg["terms"], 1)],
				"split": True,
			},
		],
		"foot": [_foot_code(cfg["annex_b_code"])],
	}
	return _form(doc, "SUBCONTRACT ORDER", cfg["subtitle"], [page1, page2, page3])


# ---------------------------------------------------------------------------
# Timesheet
# ---------------------------------------------------------------------------


def timesheet(doc):
	from altor_project.labour import row_employee

	groups, order = {}, []
	for row in doc.get("time_logs") or []:
		emp = row_employee(doc, row) or ""
		if emp not in groups:
			order.append(emp)
			groups[emp] = []
		groups[emp].append(row)
	pages = []
	for emp in order:
		rows = sorted(
			groups[emp],
			key=lambda r: get_datetime(r.from_time) if r.from_time else get_datetime("1900-01-01"),
		)
		info = (
			frappe.db.get_value(
				"Employee", emp, ["employee_name", "designation", "department", "branch"], as_dict=True
			)
			if emp
			else None
		) or frappe._dict()
		dates = [getdate(r.from_time) for r in rows if r.from_time]
		period = f"{_d(min(dates))} - {_d(max(dates))}" if dates else ""
		table, tot = [], [0, 0, 0]
		for r in rows:
			day = getdate(r.from_time) if r.from_time else None
			normal = (
				flt(r.get("custom_normal_hours"))
				if r.get("custom_normal_hours") is not None
				else flt(r.hours)
			)
			ot1, ot2 = flt(r.get("custom_ot1_hours")), flt(r.get("custom_ot2_hours"))
			tot[0] += normal
			tot[1] += ot1
			tot[2] += ot2
			site = r.get("project_name") or r.get("project") or ""
			if r.get("project") and r.get("project_name") and r.project_name != r.project:
				site = f"{r.project} - {r.project_name}"
			remarks = _join(r.get("activity_type"), strip_html(cstr(r.get("description"))), sep=" - ")
			table.append(
				{
					"cells": [
						_d(day),
						day.strftime("%a") if day else "",
						_q(normal),
						_q(ot1) if ot1 else "",
						_q(ot2) if ot2 else "",
						_e(site),
						remarks,
					]
				}
			)
		table.append({"cells": ["Total", "", _q(tot[0]), _q(tot[1]), _q(tot[2]), "", ""], "cls": "tot"})
		worker = _join(
			doc.get("custom_worker_type")
			if doc.get("custom_worker_type") != "Mixed"
			else rows[0].get("custom_worker_type"),
			rows[0].get("custom_manpower_supplier") or doc.get("custom_manpower_supplier"),
			sep=" - ",
		)
		left = [
			[
				"Employee name",
				f"<b>{_e(info.get('employee_name') or rows[0].get('custom_employee_name') or doc.get('employee_name'))}</b>",
			],
			["Designation", _e(info.get("designation"))],
			["Worker type / supplier", worker],
		]
		right = [
			["Employee ID", _e(emp)],
			["Department / site", _join(info.get("department"), info.get("branch"))],
			["Period / timesheet", _join(period, doc.name, sep="  |  ")],
		]
		pages.append(
			{
				"blocks": [
					{"t": "grid", "title": "", "left": left, "right": right},
					{
						"t": "items",
						"title": "",
						"cols": [
							["Date", 12, "c"],
							["Day", 7, "c"],
							["Regular Hours", 11, "c"],
							["OT1 Hours", 9, "c"],
							["OT2 Hours", 9, "c"],
							["Site / Project", 24, ""],
							["Remarks", 28, ""],
						],
						"rows": table,
					},
					_sign_block(
						"",
						["Employee", "Site supervisor", "Approved by"],
						[["Name / signature:", "Name / signature:", "Name / signature:"]],
						row_cls="fill tall",
					),
				],
				"foot": [_e(f"ALTOR  |  Timesheet  |  {doc.name}  |  {_status(doc)}")],
			}
		)
	if not pages:
		pages = [{"blocks": [{"t": "text", "lines": ["No time logs."]}]}]
	return _form(doc, "TIMESHEET", "", pages, header="band")


# ---------------------------------------------------------------------------
# Payslip (Salary Slip)
# ---------------------------------------------------------------------------


def payslip_days(doc):
	"""[(date, ot1, ot2, absent days)] for every day of the slip's period."""
	start, end = getdate(doc.start_date), getdate(doc.end_date)
	days = min(date_diff(end, start) + 1, 31)
	ot = {}
	if frappe.db.has_column("Timesheet Detail", "custom_ot1_hours"):
		emp_expr = (
			"COALESCE(NULLIF(td.custom_employee, ''), ts.employee)"
			if frappe.db.has_column("Timesheet Detail", "custom_employee")
			else "ts.employee"
		)
		for r in frappe.db.sql(
			f"""SELECT DATE(td.from_time) AS day, SUM(td.custom_ot1_hours) AS ot1, SUM(td.custom_ot2_hours) AS ot2
			FROM `tabTimesheet Detail` td JOIN `tabTimesheet` ts ON ts.name = td.parent
			WHERE ts.docstatus = 1 AND {emp_expr} = %(emp)s AND DATE(td.from_time) BETWEEN %(start)s AND %(end)s
			GROUP BY DATE(td.from_time)""",
			{"emp": doc.employee, "start": start, "end": end},
			as_dict=True,
		):
			ot[getdate(r.day)] = (flt(r.ot1), flt(r.ot2))
	absent = {}
	for r in frappe.get_all(
		"Attendance",
		filters={
			"employee": doc.employee,
			"docstatus": 1,
			"attendance_date": ["between", [start, end]],
			"status": ["in", ["Absent", "Half Day"]],
		},
		fields=["attendance_date", "status"],
	):
		absent[getdate(r.attendance_date)] = 1 if r.status == "Absent" else 0.5
	out = []
	for n in range(days):
		day = add_days(start, n)
		o1, o2 = ot.get(getdate(day), (0, 0))
		out.append((getdate(day), o1, o2, absent.get(getdate(day), 0)))
	return out


def payslip(doc):
	earnings = [
		(e.salary_component, e.amount)
		for e in doc.get("earnings") or []
		if not e.get("statistical_component")
	]
	deductions = [(e.salary_component, e.amount) for e in doc.get("deductions") or [] if flt(e.amount)]
	n = max(len(earnings), len(deductions), 6)
	pay_rows = []
	for i in range(n):
		e = earnings[i] if i < len(earnings) else ("", None)
		d = deductions[i] if i < len(deductions) else ("", None)
		pay_rows.append(
			{
				"cells": [
					_e(e[0]),
					_m(e[1]) if e[1] is not None else "",
					_e(d[0]),
					_m(d[1]) if d[1] is not None else "",
				]
			}
		)
	cur = _e(doc.get("currency") or "AED")
	pay_rows.append(
		{
			"cells": ["Gross pay", _m(doc.gross_pay), "Total deductions", _m(doc.total_deduction)],
			"cls": "calc",
		}
	)
	method = "Bank transfer" if doc.get("bank_account_no") or doc.get("bank_name") else "Cash"
	if doc.get("bank_name"):
		method += f" - {doc.bank_name}"
	days = payslip_days(doc)
	half = (len(days) + 1) // 2
	day_rows, tot = [], [0, 0, 0]
	for i in range(half):
		cells = []
		for d in (days[i], days[i + half] if i + half < len(days) else None):
			if d:
				cells += [
					_d(d[0]),
					_q(d[1]) if d[1] else "",
					_q(d[2]) if d[2] else "",
					_q(d[3]) if d[3] else "",
				]
				tot[0] += d[1]
				tot[1] += d[2]
				tot[2] += d[3]
			else:
				cells += ["", "", "", ""]
		day_rows.append({"cells": cells})
	day_rows.append(
		{"cells": ["Period totals", _q(tot[0]), _q(tot[1]), _q(tot[2]), "", "", "", ""], "cls": "tot"}
	)
	emp = frappe.db.get_value("Employee", doc.employee, ["branch"], as_dict=True) or frappe._dict()
	left = [
		["Employee name", f"<b>{_e(doc.employee_name)}</b>"],
		["Designation", _e(doc.get("designation"))],
		["Period start", _d(doc.start_date)],
		["Payment date", _d(doc.posting_date)],
	]
	right = [
		["Employee ID", _e(doc.employee)],
		["Department / Site", _join(doc.get("department"), emp.get("branch"))],
		["Period end", _d(doc.end_date)],
		["Payment method", _e(method)],
	]
	net = flt(doc.get("rounded_total") or doc.get("net_pay"))
	blocks = [
		{"t": "grid", "title": "", "left": left, "right": right},
		{
			"t": "items",
			"title": "",
			"cols": [["EARNINGS", 34, ""], [cur, 16, "r"], ["DEDUCTIONS", 34, ""], [cur, 16, "r"]],
			"rows": pay_rows,
			"fill": [1, 3],
		},
		{
			"t": "totals",
			"left": [
				f"<b>In words:</b> {_e(doc.get('total_in_words') or money_in_words(net, doc.get('currency')))}"
			],
			"rows": [[f"NET PAY &nbsp;&bull;&nbsp; {cur}", _m(net), "navy"]],
			"left_width": 55,
		},
		{
			"t": "items",
			"title": "DAILY OVERTIME DETAILS",
			"cols": [
				["Date", 14, "c"],
				["OT1 (hrs)", 9, "c"],
				["OT2 (hrs)", 9, "c"],
				["Abs. (days)", 9, "c"],
				["Date", 14, "c"],
				["OT1 (hrs)", 9, "c"],
				["OT2 (hrs)", 9, "c"],
				["Abs. (days)", 9, "c"],
			],
			"rows": day_rows,
			"fill": [1, 2, 3, 5, 6, 7],
		},
		_sign_block(
			"",
			["Prepared by", "Approved by", "Receiver's signature"],
			[[_user(doc.owner), "", ""]],
			row_cls="fill tall",
		),
	]
	return _form(
		doc,
		"MONTHLY PAYSLIP",
		"",
		[{"blocks": blocks, "foot": [_e(f"ALTOR  |  Payslip  |  {doc.name}")]}],
		header="band",
	)


# ---------------------------------------------------------------------------
# Payment Certificate
# ---------------------------------------------------------------------------


def payment_certificate(doc):
	def pair(no, validity):
		return _join(no, _d(validity), sep="  /  ")

	g1 = (
		[
			["Subcontractor / Payee", f"<b>{_e(doc.supplier_name or doc.supplier)}</b>"],
			["Agreement Reference", _e(doc.get("subcontract_work_order"))],
			["Subcontract Type", _e(doc.get("subcontract_type"))],
			["Site / Project", _join(doc.project, doc.get("project_name"), sep=" - ")],
			["Scope of Work", _e(doc.get("scope_of_work"))],
			["Project / Budget Code", _join(doc.get("project_budget"), doc.get("cost_center"))],
		],
		[
			["Certificate No.", f"<b>{_e(doc.name)}</b>"],
			["Certificate Date", _d(doc.get("certificate_date"))],
			["Application No.", _e(doc.get("application_no"))],
			["Application Date", _d(doc.get("application_date"))],
			["Application Recorded", _d(doc.get("application_recorded"))],
			["Payment Due Date", _d(doc.get("payment_due_date"))],
		],
	)
	g2 = (
		[
			["APG No. &amp; Validity", pair(doc.apg_no, doc.apg_validity)],
			["PG No. &amp; Validity", pair(doc.pg_no, doc.pg_validity)],
			["TPL No. &amp; Validity", pair(doc.tpl_no, doc.tpl_validity)],
			[
				"Vehicle Insurance &amp; Validity",
				pair(doc.vehicle_insurance_no, doc.vehicle_insurance_validity),
			],
			["Trade License &amp; Validity", pair(doc.trade_license_no, doc.trade_license_validity)],
		],
		[
			["WC Insurance No. &amp; Validity", pair(doc.wc_insurance_no, doc.wc_insurance_validity)],
			["CPM Insurance No. &amp; Validity", pair(doc.cpm_insurance_no, doc.cpm_insurance_validity)],
			["PI No. &amp; Validity", pair(doc.pi_no, doc.pi_validity)],
			["Cargo Insurance &amp; Validity", pair(doc.cargo_insurance_no, doc.cargo_insurance_validity)],
			["VAT Certificate / TRN", _e(doc.get("vat_trn"))],
		],
	)
	cur = _e(doc.get("currency") or "AED")
	g3 = (
		[
			["Subcontract Amount", _m(doc.subcontract_amount)],
			["Approved Amendments / Variations", _m(doc.approved_variations)],
			["Other Adjustments", _m(doc.other_adjustments)],
			["Revised Contract Amount", f"<b>{_m(doc.revised_contract_amount)}</b>"],
			["Settlement / Waiver Figure", _m(doc.settlement_figure, True)],
		],
		[
			["Month", _e(doc.get("period_month"))],
			["Duration", _e(doc.get("duration"))],
			["Commencement Date", _d(doc.get("commencement_date"))],
			[
				"Cumulative Work %",
				_pct(doc.cumulative_work_percent) if flt(doc.get("cumulative_work_percent")) else "",
			],
			["Currency", cur],
		],
	)
	lines = {r.ref: r for r in doc.get("lines") or []}

	def line(ref):
		r = lines.get(ref)
		if not r:
			return None
		return {
			"cells": [
				_e(r.description),
				ref,
				_pct(r.rate) if flt(r.get("rate")) else "",
				_m(r.cumulative),
				_m(r.previous),
				_m(r.this_period),
				_e(r.get("notes")),
			]
		}

	def calc(label, ref, key, rate="", cls="calc"):
		return {
			"cells": [
				label,
				ref,
				rate,
				_m(doc.get(key + "_cumulative")),
				_m(doc.get(key + "_previous")),
				_m(doc.get(key + "_this_period")),
				"",
			],
			"cls": cls,
		}

	cert = [line(x) for x in "ABCD"] + [calc("GROSS AMOUNT", "E", "gross")] + [line(x) for x in "FG"]
	cert += [calc("Remaining Advance Payment", "H", "remaining_advance", cls="")] + [line(x) for x in "IJKL"]
	cert += [
		calc("TOTAL DEDUCTIONS", "O", "total_deductions"),
		calc("NET AMOUNT (EXCL. VAT)", "P", "net_excl_vat"),
		calc("VATABLE TURNOVER", "Q", "net_excl_vat", cls=""),
		calc("VAT", "R", "vat_amount", _pct(doc.vat_rate)),
		calc("NET AMOUNT INCLUDING VAT", "S", "net_incl_vat", cls="grand"),
	]
	back = [
		{
			"cells": [
				_e(r.description),
				_e(r.get("reference")),
				_d(r.get("date")),
				_m(r.amount),
				_m(r.vat),
				_m(r.total),
				_e(r.get("remarks")),
			]
		}
		for r in doc.get("back_charges") or []
	]
	if back:
		back.append(
			{"cells": ["Total Back Charges", "", "", "", "", _m(doc.total_back_charges), ""], "cls": "calc"}
		)
	users = [
		doc.get(f) for f in ("initiated_by", "reviewed_by", "checked_by", "authorized_by", "approved_by")
	]
	stamp = (
		frappe.db.get_value("Company", doc.company, "custom_company_stamp")
		if doc.get("company") and frappe.db.has_column("Company", "custom_company_stamp")
		else None
	)
	blocks = [
		{"t": "grid", "title": "", "left": g1[0], "right": g1[1], "wide": True},
		{"t": "grid", "title": "", "left": g2[0], "right": g2[1], "wide": True},
		{"t": "grid", "title": "", "left": g3[0], "right": g3[1], "wide": True},
		{
			"t": "items",
			"title": f"PAYMENT CERTIFICATION &nbsp;|&nbsp; {cur}",
			"cols": [
				["Description", 30, ""],
				["Ref.", 5, "c"],
				["Rate / %", 8, "r"],
				["Cumulative", 13, "r"],
				["Previous", 13, "r"],
				["This Period", 13, "r"],
				["Notes", 18, ""],
			],
			"rows": [r for r in cert if r],
		},
		{"t": "words", "rows": [["AMOUNT IN WORDS:", _e(doc.get("in_words"))]]},
		{
			"t": "items",
			"title": "BACK CHARGES / OTHER RECOVERIES",
			"cols": [
				["Description", 26, ""],
				["Reference", 13, ""],
				["Date", 11, ""],
				["Amount", 12, "r"],
				["VAT", 10, "r"],
				["Total", 12, "r"],
				["Remarks", 16, ""],
			],
			"rows": back,
			"pad": 0 if back else 2,
		},
		{
			"t": "words",
			"rows": [
				["PAYMENT TERMS / NOTES:", _e(doc.get("payment_terms"))],
				["REMARKS:", _e(doc.get("remarks"))],
			],
		},
		{
			"t": "items",
			"title": "",
			"cols": [
				["INITIATED BY", 15, "c"],
				["REVIEWED BY", 15, "c"],
				["CHECKED BY", 15, "c"],
				["AUTHORIZED BY", 15, "c"],
				["APPROVED BY", 15, "c"],
				["DATE", 12, "c"],
				["STAMP", 13, "c"],
			],
			"rows": [
				{
					"cells": ["<div style='height:40px'></div>"] * 6
					+ [
						f"<img src='{stamp}' style='max-height:44px;max-width:90px'>"
						if stamp and doc.docstatus == 1
						else ""
					]
				},
				{
					"cells": [(_user(u) or "") + "<div class='mu'>Name / Sign</div>" for u in users]
					+ [_d(doc.get("approved_on")), ""]
				},
			],
		},
		{
			"t": "words",
			"rows": [
				[
					"ERP fields:",
					_join(
						f"Project ID: {doc.project}",
						f"Client PO: {doc.get('client_po') or '-'}",
						f"Payment Application: {doc.get('application_no') or '-'}",
						f"Certificate No.: {doc.name}",
						f"Version: {doc.get('version') or 1}",
						f"Approval Status: {doc.get('approval_status') or ''}",
						sep="  |  ",
					),
				]
			],
		},
	]
	return _form(doc, "SUBCONTRACTOR'S PAYMENT CERTIFICATE", "", [{"blocks": blocks}], header="certificate")


BUILDERS = {
	"tax_invoice": tax_invoice,
	"purchase_order": purchase_order,
	"delivery_note": delivery_note,
	"asset_allocation": asset_allocation,
	"asset_return": asset_return,
	"supplier_return": supplier_return,
	"subcontract_order": subcontract_order,
	"timesheet": timesheet,
	"payslip": payslip,
	"payment_certificate": payment_certificate,
}

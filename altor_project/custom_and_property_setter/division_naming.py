# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Division based document numbers that keep one sequence through the sales flow.

    Lead          CRM-SCF-LEAD-2026-0007
    Quotation     QT-SCF-2026-0007      (made from that lead)
    Sales Order   SO-SCF-2026-0007      (made from that quotation)
    Project       PRJ-SCF-2026-0007     (made from that sales order)

* {division} is the Division Code of the document's Division (Cost Center), e.g. SCF.
* Each division has its own counter per year. A document that starts a new enquiry
  (a Lead, or a Quotation / Sales Order / Project not made from an earlier step)
  takes the next number; a document made from an earlier step reuses its number.
* The shared part is stored on each document as "Division Ref No." (SCF-2026-0007).
* A second document from the same source gets a suffix (QT-SCF-2026-0007-V2).
  Amendments keep their standard revision names.
* Formats, number of digits and on/off are set in Altor Settings > Division Numbering.
  Without a division the document keeps its standard naming series.
"""

import re

import frappe
from frappe import _
from frappe.model.naming import getseries
from frappe.utils import cint, getdate, nowdate

REF_FIELD = "custom_division_ref"

DEFAULT_FORMATS = {
	"Lead": "CRM-{division}-LEAD-{year}-{seq}",
	"Quotation": "QT-{division}-{year}-{seq}",
	"Sales Order": "SO-{division}-{year}-{seq}",
	"Project": "PRJ-{division}-{year}-{seq}",
}
SETTING_FIELDS = {
	"Lead": "lead_number_format",
	"Quotation": "quotation_number_format",
	"Sales Order": "sales_order_number_format",
	"Project": "project_number_format",
}
DATE_FIELDS = {
	"Lead": None,
	"Quotation": "transaction_date",
	"Sales Order": "transaction_date",
	"Project": "expected_start_date",
}
# Codes used when a Division (Cost Center) has no Division Code set
KNOWN_CODES = {
	"scaffolding": "SCF",
	"cradle": "CRD",
	"equipment rental": "EQR",
	"rope access": "RPA",
	"construction hoist": "CHS",
	"mast climber": "MCL",
	"trading": "TRD",
	"manpower": "MPW",
}


def get_settings():
	s = frappe.get_cached_doc("Altor Settings")
	enabled = s.get("enable_division_numbering")
	return frappe._dict(
		enabled=1 if enabled is None else cint(enabled),
		digits=cint(s.get("division_series_digits")) or 4,
		formats={dt: (s.get(field) or DEFAULT_FORMATS[dt]) for dt, field in SETTING_FIELDS.items()},
	)


def division_code(cost_center):
	"""Short code of a division: its Division Code, else a known code, else initials."""
	if not cost_center:
		return None
	fields = ["cost_center_name", "cost_center_number"]
	if frappe.db.has_column("Cost Center", "custom_division_code"):
		fields.append("custom_division_code")
	values = frappe.db.get_value("Cost Center", cost_center, fields, as_dict=True)
	if not values:
		return None
	code = values.get("custom_division_code") or values.get("cost_center_number")
	if not code:
		name = (values.get("cost_center_name") or cost_center).strip().lower()
		code = KNOWN_CODES.get(name)
		if not code:
			words = re.findall(r"[a-z0-9]+", name)
			code = "".join(w[0] for w in words)[:3] if len(words) > 1 else (words[0][:3] if words else "DIV")
	return re.sub(r"[^A-Za-z0-9]", "", code).upper() or "DIV"


def _ref_of(doctype, name):
	if not name or not frappe.db.has_column(doctype, REF_FIELD):
		return None
	return frappe.db.get_value(doctype, name, REF_FIELD)


def source_ref(doc):
	"""Division Ref No. of the document this one was made from, if any."""
	if doc.doctype == "Quotation":
		if doc.get("quotation_to") == "Lead":
			return _ref_of("Lead", doc.get("party_name"))
	elif doc.doctype == "Sales Order":
		for row in doc.get("items") or []:
			if row.get("prevdoc_docname"):
				return _ref_of("Quotation", row.prevdoc_docname)
	elif doc.doctype == "Project":
		return _ref_of("Sales Order", doc.get("sales_order")) or _ref_of("Quotation", doc.get("quotation"))
	return None


def split_ref(ref):
	"""'SCF-2026-0007' -> ('SCF', '2026', '0007')."""
	parts = (ref or "").rsplit("-", 2)
	return tuple(parts) if len(parts) == 3 else (None, None, None)


def new_ref(doctype, code, doc, digits):
	date_field = DATE_FIELDS.get(doctype)
	year = getdate((doc.get(date_field) if date_field else None) or nowdate()).year
	seq = getseries(f"ALTOR-DIV-{code}-{year}-", digits)
	return f"{code}-{year}-{seq}"


def build_name(fmt, code, year, seq):
	try:
		return fmt.format(division=code, year=year, seq=seq)
	except (KeyError, IndexError, ValueError):
		frappe.throw(
			_("Invalid number format {0} in Altor Settings. Use {{division}}, {{year}} and {{seq}}.").format(
				frappe.bold(fmt)
			)
		)


def unique_name(doctype, name):
	if not frappe.db.exists(doctype, name):
		return name
	# "-V2", not "-2": quotation revisions are named "-R1", "-R2" and a bare "-2" is
	# treated as an amendment suffix by the revision renaming (events/quotation.py)
	i = 2
	while frappe.db.exists(doctype, f"{name}-V{i}"):
		i += 1
	return f"{name}-V{i}"


def set_division_name(doc, method=None):
	"""doc_event (autoname) for Lead, Quotation, Sales Order and Project."""
	if doc.get("amended_from") or doc.doctype not in DEFAULT_FORMATS:
		return
	settings = get_settings()
	if not settings.enabled:
		return

	code = division_code(doc.get("cost_center"))
	ref = source_ref(doc)
	ref_code, year, seq = split_ref(ref)
	if not ref_code or (code and ref_code != code):
		# nothing to continue from (or the division was changed): start a new number
		if not code:
			return  # no division: keep the standard naming series
		ref = new_ref(doc.doctype, code, doc, settings.digits)
		ref_code, year, seq = split_ref(ref)

	doc.name = unique_name(doc.doctype, build_name(settings.formats[doc.doctype], ref_code, year, seq))
	if doc.meta.has_field(REF_FIELD):
		doc.set(REF_FIELD, ref)


def keep_ref_on_amend(doc, method=None):
	"""doc_event (validate): an amended document keeps the original's Division Ref No."""
	if doc.get("amended_from") and doc.meta.has_field(REF_FIELD) and not doc.get(REF_FIELD):
		doc.set(REF_FIELD, _ref_of(doc.doctype, doc.amended_from))

import frappe
from frappe import _
from frappe.utils import cint


def quotation_required():
	"""Altor Settings > Sales Order Only from Quotation (on unless switched off)."""
	value = frappe.get_cached_doc("Altor Settings").get("sales_order_from_quotation_only")
	return 1 if value is None else cint(value)


def require_quotation(doc, method=None):
	"""doc_event (validate): every Sales Order line comes from a submitted Quotation.

	Lines get the Quotation in prevdoc_docname when the order is made with Quotation > Create >
	Sales Order (or Get Items From > Quotation). Set doc.flags.ignore_quotation_check to skip.
	"""
	if doc.flags.ignore_quotation_check or not quotation_required():
		return
	missing = [row for row in doc.get("items") or [] if not row.get("prevdoc_docname")]
	if not missing:
		return
	lines = "".join(
		f"<li>{_('Row #{0}: {1}').format(row.idx, frappe.bold(row.item_code or row.item_name or ''))}</li>"
		for row in missing
	)
	frappe.throw(
		_(
			"A Sales Order is made from a submitted Quotation: open the Quotation and use Create > Sales Order, or Get Items From > Quotation here. These lines are not from a quotation:"
		)
		+ f"<ul>{lines}</ul>",
		title=_("Quotation Required"),
	)


def on_submit(doc, method=None):
	"""doc_event (Sales Order on_submit): the leads of its quotations are Converted."""
	from altor_project.events.lead import mark_converted

	quotations = {row.prevdoc_docname for row in doc.get("items") or [] if row.get("prevdoc_docname")}
	for quotation in quotations:
		party = frappe.db.get_value("Quotation", quotation, ["quotation_to", "party_name"], as_dict=True)
		if party and party.quotation_to == "Lead" and party.party_name:
			mark_converted(party.party_name)

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

from altor_project.custom_and_property_setter.custom_field import CREATE_FIELDS
from altor_project.custom_and_property_setter.print_fields import PRINT_FIELDS

# Sales Invoice and Purchase Order defaults are in the app's custom/*.json (synced on migrate)
DEFAULT_FORMATS = {
	"Delivery Note": "Altor Delivery Note",
	"Timesheet": "Altor Timesheet",
	"Salary Slip": "Altor Payslip",
}


def execute():
	"""ALTOR print designs: fields they print, default print formats, company contact details."""
	create_custom_fields({dt: CREATE_FIELDS[dt] for dt in PRINT_FIELDS}, ignore_validate=True, update=True)
	for doctype, print_format in DEFAULT_FORMATS.items():
		if frappe.db.exists("Print Format", print_format):
			make_property_setter(
				doctype,
				None,
				"default_print_format",
				print_format,
				"Data",
				for_doctype=True,
				validate_fields_for_doctype=False,
			)
	for company in frappe.get_all("Company", pluck="name"):
		fill_company_details(company)
	add_letter_head()


def fill_company_details(company):
	"""Phone, email, website and the office address of the ALTOR company, where they are empty
	(values from the client's company details sheet; edit them on the Company / Address)."""
	from altor_project.print_forms import DEFAULTS, _plain

	if _plain(frappe.db.get_value("Company", company, "company_name")) != _plain(DEFAULTS["name"]):
		return
	values = {}
	for field, value in (
		("phone_no", DEFAULTS["phone"]),
		("email", DEFAULTS["email"]),
		("website", "https://" + DEFAULTS["website"]),
	):
		if not frappe.db.get_value("Company", company, field):
			values[field] = value
	if values:
		frappe.db.set_value("Company", company, values)

	has_address = frappe.db.get_value(
		"Dynamic Link", {"link_doctype": "Company", "link_name": company, "parenttype": "Address"}, "parent"
	)
	if has_address or not frappe.db.exists("Country", "United Arab Emirates"):
		return
	try:
		frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": DEFAULTS["name"],
				"address_type": "Office",
				"address_line1": "Office 130, Al Fahim Building",
				"address_line2": "Musaffah M4",
				"city": "Abu Dhabi",
				"country": "United Arab Emirates",
				"pincode": DEFAULTS["po_box"],
				"phone": DEFAULTS["phone"],
				"email_id": DEFAULTS["email"],
				"is_your_company_address": 1,
				"is_primary_address": 1,
				"links": [{"link_doctype": "Company", "link_name": company}],
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title=f"ALTOR print formats: company address for {company}")


LETTER_HEAD = "ALTOR"
LOGO = "/assets/altor_project/images/altor_logo.png"


def add_letter_head():
	"""An ALTOR letter head (logo, tagline, company line) for letters and the standard print formats.
	Not made the default: the ALTOR print formats draw their own header."""
	if frappe.db.exists("Letter Head", LETTER_HEAD):
		return
	from altor_project.print_forms import DEFAULTS

	d = DEFAULTS
	try:
		frappe.get_doc(
			{
				"doctype": "Letter Head",
				"letter_head_name": LETTER_HEAD,
				"source": "HTML",
				"content": (
					'<table style="width:100%;border-bottom:2.5px solid #f2b300"><tr>'
					f'<td style="vertical-align:bottom;padding-bottom:6px"><img src="{LOGO}" style="height:52px"></td>'
					'<td style="text-align:right;vertical-align:bottom;padding-bottom:6px;color:#082f52;'
					'font-weight:700;font-size:10pt">Your Access Needs.<br>Our Expertise.</td></tr></table>'
				),
				"footer_source": "HTML",
				"footer": (
					'<div style="border-top:1px solid #082f52;text-align:center;font-size:8pt;color:#18344c;padding-top:4px">'
					f'<b style="color:#082f52">{d["name"]}</b><br>{d["address"]} &nbsp;|&nbsp; P.O. Box {d["po_box"]}<br>'
					f"{d['phone']} &nbsp;&bull;&nbsp; {d['email']} &nbsp;&bull;&nbsp; <b>{d['website']}</b></div>"
				),
				"is_default": 0,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="ALTOR print formats: letter head")

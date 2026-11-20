import frappe
from erpnext.crm.doctype.lead.lead import Lead

SITE_VISIT_DONE = "Site Visit Completed"
# a site visit moves a lead forward only from these; a quoted / converted lead keeps its status
EARLY_STATUSES = ("Lead", "Open", "Replied", "Opportunity", "Interested")


def update_lead_status(lead_name, status):
	if not lead_name:
		return
	current_status = frappe.db.get_value("Lead", lead_name, "status")
	if current_status and current_status != status:
		frappe.db.set_value("Lead", lead_name, "status", status, update_modified=False)


def on_site_visit_submit(doc, method=None):
	"""doc_event (Site Visit on_submit): the lead becomes "Site Visit Completed"."""
	if doc.lead and frappe.db.get_value("Lead", doc.lead, "status") in EARLY_STATUSES:
		update_lead_status(doc.lead, SITE_VISIT_DONE)


def on_site_visit_cancel(doc, method=None):
	"""doc_event (Site Visit on_cancel): back to Open when no other submitted visit remains."""
	if not doc.lead or frappe.db.get_value("Lead", doc.lead, "status") != SITE_VISIT_DONE:
		return
	other = frappe.db.exists("Site Visit", {"lead": doc.lead, "docstatus": 1, "name": ["!=", doc.name]})
	if not other:
		update_lead_status(doc.lead, "Open")


# ---------------------------------------------------------------------------
# Quotations of a lead
# ---------------------------------------------------------------------------


def customer_of_lead(lead_name, link=False):
	"""The customer an order from this lead is booked on.

	The lead's Existing Customer when set, else the customer made from the lead. With link=True the
	existing customer is pointed at this lead (Customer > Lead), which is how ERPNext finds it when a
	Sales Order is made from the quotation, so no duplicate customer is created.
	"""
	if not lead_name:
		return None
	customer = frappe.db.get_value("Lead", lead_name, "customer")
	if customer and frappe.db.exists("Customer", customer):
		if link and frappe.db.get_value("Customer", customer, "lead_name") != lead_name:
			frappe.db.set_value("Customer", customer, "lead_name", lead_name, update_modified=False)
		return customer
	return frappe.db.get_value("Customer", {"lead_name": lead_name})


def refresh_quotation_status(doc, method=None):
	"""doc_event (Quotation after_insert / on_submit / on_cancel / on_trash): a lead with a quotation
	(draft or submitted) is "Quotation"; without one it goes back to Site Visit Completed or Open.
	Later stages (Converted, Lost Quotation, Do Not Contact) are left alone."""
	if doc.get("quotation_to") != "Lead" or not doc.get("party_name"):
		return
	lead = doc.party_name
	status = frappe.db.get_value("Lead", lead, "status")
	gone = method in ("on_cancel", "on_trash")
	active = frappe.db.exists(
		"Quotation",
		{
			"quotation_to": "Lead",
			"party_name": lead,
			"docstatus": ["<", 2],
			"status": ["!=", "Lost"],
			"name": ["!=", doc.name if gone else ""],
		},
	)
	if active and status in (*EARLY_STATUSES, SITE_VISIT_DONE):
		update_lead_status(lead, "Quotation")
	elif not active and status == "Quotation":
		visited = frappe.db.exists("Site Visit", {"lead": lead, "docstatus": 1})
		update_lead_status(lead, SITE_VISIT_DONE if visited else "Open")


def mark_converted(lead_name):
	"""The lead's quotation became a submitted Sales Order."""
	status = frappe.db.get_value("Lead", lead_name, "status")
	if status in (*EARLY_STATUSES, SITE_VISIT_DONE, "Quotation"):
		update_lead_status(lead_name, "Converted")


# Lead form (Altor): "First Name" is labelled Company Name and "Contact Name" (custom_contact_name)
# holds the person; Middle / Last Name are hidden.


class CustomLead(Lead):
	def validate(self):
		if self.customer:
			# a lead for an existing customer: its name is the company, source "Existing Customer"
			if not self.first_name:
				self.first_name = frappe.db.get_value("Customer", self.customer, "customer_name")
			if not self.source and frappe.db.exists("Lead Source", "Existing Customer"):
				self.source = "Existing Customer"
		# the company in the Organization Name too, so the lead converts to a Company customer of that name
		if self.first_name:
			self.company_name = self.first_name
		super().validate()

	def create_contact(self):
		"""The lead's Contact is the person in Contact Name, at the company (standard: the First Name)."""
		person = (self.get("custom_contact_name") or "").strip()
		if not person:
			return super().create_contact()
		if self.first_name:
			self.company_name = self.first_name
		if not self.lead_name:
			self.set_full_name()
			self.set_lead_name()
		company, last_name = self.first_name, self.last_name
		self.first_name, self.last_name = person, None
		try:
			return super().create_contact()
		finally:
			self.first_name, self.last_name = company, last_name

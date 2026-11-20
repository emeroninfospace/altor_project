import frappe
from erpnext.crm.doctype.lead.lead import Lead


def update_lead_status(lead_name, status):
	if not lead_name:
		return
	current_status = frappe.db.get_value("Lead", lead_name, "status")
	if current_status and current_status != status:
		frappe.db.set_value("Lead", lead_name, "status", status, update_modified=False)


def on_site_visit_submit(doc, method=None):
	update_lead_status(doc.lead, "Site Visit Completed")


# Lead form (Altor): "First Name" is labelled Company Name and "Contact Name" (custom_contact_name)
# holds the person; Middle / Last Name are hidden.


class CustomLead(Lead):
	def validate(self):
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

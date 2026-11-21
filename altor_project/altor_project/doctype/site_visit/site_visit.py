# Copyright (c) 2026, emeron and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SiteVisit(Document):
	def before_insert(self):
		# before the number is given: the division (and so SV-SCF-...) comes from the lead
		self.set_from_lead()

	def validate(self):
		self.set_from_lead()

	def before_submit(self):
		# a submitted visit is done (the lead becomes "Site Visit Completed")
		if self.status in (None, "", "Draft"):
			self.status = "Closed"

	def before_cancel(self):
		self.status = "Cancelled"

	def set_from_lead(self):
		"""Lead name (company) and division from the lead, when not filled in."""
		if not self.lead:
			return
		lead = frappe.db.get_value(
			"Lead", self.lead, ["lead_name", "company_name", "cost_center"], as_dict=True
		)
		if not lead:
			return
		self.lead_name = lead.company_name or lead.lead_name
		if not self.cost_center and lead.cost_center:
			self.cost_center = lead.cost_center

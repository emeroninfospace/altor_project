# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Subcontractor's Payment Certificate (ALTOR template).

Lines are entered as cumulative amounts to date. "Previous" is the cumulative of the
last submitted certificate for the same agreement (Subcontract Work Order), else for the
same subcontractor and project, and "This Period" = Cumulative - Previous.

    E  Gross Amount            = A + B + C + D
    H  Remaining Advance       = F - G
    O  Total Deductions        = G + I + J - K - L
    P  Net Amount excl. VAT    = E + F - O
    Q  Vatable Turnover        = P
    R  VAT                     = Q x VAT rate
    S  Net Amount incl. VAT    = P + R
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt, getdate, money_in_words, nowdate

# (ref, description) of the lines that are entered; E, H, O, P, Q, R, S are calculated
LINE_DEFS = (
	("A", "Works Executed"),
	("B", "Variations"),
	("C", "Material on Site"),
	("D", "Dayworks"),
	("F", "Advance Payment"),
	("G", "Recovery of Advance"),
	("I", "Retention on Works"),
	("J", "Retention in Lieu of Performance Bond"),
	("K", "Release of Retention"),
	("L", "Financial Assistance / On Account"),
)
# Lines whose cumulative is worked out from Rate % x (Works Executed + Variations)
RATE_LINES = ("G", "I", "J")
COLUMNS = ("cumulative", "previous", "this_period")

APPROVAL_STEPS = {
	"Initiated": "initiated_by",
	"Reviewed": "reviewed_by",
	"Checked": "checked_by",
	"Authorized": "authorized_by",
	"Approved": "approved_by",
}
# Authorizing and approving is limited to these roles
APPROVER_ROLES = ("Projects Manager", "Accounts Manager", "System Manager")

SECURITIES = (
	("apg", "APG"),
	("pg", "PG"),
	("tpl", "TPL"),
	("vehicle_insurance", "Vehicle Insurance"),
	("trade_license", "Trade License"),
	("wc_insurance", "WC Insurance"),
	("cpm_insurance", "CPM Insurance"),
	("pi", "PI"),
	("cargo_insurance", "Cargo Insurance"),
)
EXPIRY_NOTICE_DAYS = 30


def calculate_summary(values, vat_rate):
	"""Calculated lines from {ref: amount} for one column."""
	v = {ref: flt(values.get(ref)) for ref, _label in LINE_DEFS}
	gross = v["A"] + v["B"] + v["C"] + v["D"]
	deductions = v["G"] + v["I"] + v["J"] - v["K"] - v["L"]
	net = gross + v["F"] - deductions
	vat = flt(net * flt(vat_rate) / 100, 2)
	return frappe._dict(
		gross=flt(gross, 2),
		remaining_advance=flt(v["F"] - v["G"], 2),
		total_deductions=flt(deductions, 2),
		net_excl_vat=flt(net, 2),
		vat_amount=vat,
		net_incl_vat=flt(net + vat, 2),
	)


def previous_certificate(doc, exclude=None):
	"""Last submitted certificate this one follows (same agreement, else subcontractor + project)."""
	filters = chain_filters(doc)
	if not filters:
		return None
	filters.update({"docstatus": 1, "certificate_date": ["<=", doc.get("certificate_date") or nowdate()]})
	if exclude:
		filters["name"] = ["!=", exclude]
	rows = frappe.get_all(
		"Payment Certificate",
		filters=filters,
		fields=["name"],
		order_by="certificate_date desc, creation desc",
		limit=1,
	)
	return rows[0].name if rows else None


def chain_filters(doc):
	"""Certificates that follow one another: same agreement, else same subcontractor and project."""
	if doc.get("subcontract_work_order"):
		return {"subcontract_work_order": doc.subcontract_work_order}
	if doc.get("supplier") and doc.get("project"):
		return {"supplier": doc.supplier, "project": doc.project, "subcontract_work_order": ["is", "not set"]}
	return {}


def previous_values(certificate):
	if not certificate:
		return {}
	return {
		r.ref: flt(r.cumulative)
		for r in frappe.get_all(
			"Payment Certificate Line",
			filters={"parent": certificate, "parenttype": "Payment Certificate"},
			fields=["ref", "cumulative"],
		)
	}


class PaymentCertificate(Document):
	def validate(self):
		self.set_defaults()
		self.validate_agreement()
		self.set_lines()
		self.set_previous()
		self.apply_rates()
		self.calculate()
		self.calculate_back_charges()
		self.set_approval()
		self.set_version()
		if not self.flags.ignore_certificate_warnings:
			self.show_warnings()

	def before_submit(self):
		if self.approval_status != "Approved":
			frappe.throw(
				_("Set Approval Status to Approved before submitting the certificate."),
				title=_("Not Approved"),
			)

	def on_cancel(self):
		later = frappe.get_all(
			"Payment Certificate",
			filters={
				"docstatus": 1,
				"name": ["!=", self.name],
				"certificate_date": [">=", self.certificate_date],
				**chain_filters(self),
			},
			pluck="name",
		)
		if later:
			frappe.msgprint(
				_(
					"Later certificates {0} took their Previous figures from this one. Amend them as well."
				).format(", ".join(later)),
				title=_("Check Later Certificates"),
				indicator="orange",
			)

	# ------------------------------------------------------------------ setup

	def set_defaults(self):
		if not self.currency and self.company:
			self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
		if self.vat_rate is None:
			self.vat_rate = 5
		if not self.period_month and self.certificate_date:
			self.period_month = getdate(self.certificate_date).strftime("%b %Y")
		if (
			self.payment_due_date
			and self.certificate_date
			and getdate(self.payment_due_date) < getdate(self.certificate_date)
		):
			frappe.throw(_("Payment Due Date cannot be before the Certificate Date."))

	def validate_agreement(self):
		if not self.subcontract_work_order:
			return
		wo = frappe.db.get_value(
			"Subcontract Work Order",
			self.subcontract_work_order,
			["supplier", "project", "docstatus"],
			as_dict=True,
		)
		if not wo:
			return
		if wo.docstatus == 2:
			frappe.throw(_("Subcontract Work Order {0} is cancelled.").format(self.subcontract_work_order))
		if wo.supplier and wo.supplier != self.supplier:
			frappe.throw(
				_("Agreement {0} is with {1}, not {2}.").format(
					self.subcontract_work_order, frappe.bold(wo.supplier), frappe.bold(self.supplier)
				)
			)
		if wo.project and wo.project != self.project:
			frappe.throw(
				_("Agreement {0} is for project {1}, not {2}.").format(
					self.subcontract_work_order, frappe.bold(wo.project), frappe.bold(self.project)
				)
			)

	def set_lines(self):
		"""Keep the fixed certification lines A..L, in order, keeping entered values."""
		existing = {row.ref: row for row in self.get("lines") or [] if row.ref}
		rows = []
		for ref, label in LINE_DEFS:
			row = existing.get(ref)
			values = row.as_dict() if row else {}
			rows.append(
				{
					"ref": ref,
					"description": label,
					"rate": flt(values.get("rate")),
					"cumulative": flt(values.get("cumulative")),
					"notes": values.get("notes"),
					"currency": self.currency,
					"name": values.get("name"),
				}
			)
		if [r.ref for r in self.get("lines") or []] == [r["ref"] for r in rows]:
			for row, values in zip(self.lines, rows, strict=True):
				row.description = values["description"]
				row.currency = self.currency
		else:
			self.set("lines", [])
			for values in rows:
				values.pop("name")
				self.append("lines", values)

	def set_previous(self):
		self.previous_certificate = previous_certificate(self, exclude=None if self.is_new() else self.name)
		previous = previous_values(self.previous_certificate)
		for row in self.lines:
			row.previous = flt(previous.get(row.ref), 2)

	def apply_rates(self):
		"""Rate % on G, I and J works out the cumulative from Works Executed + Variations."""
		lines = {row.ref: row for row in self.lines}
		base = flt(lines["A"].cumulative) + flt(lines["B"].cumulative)
		for ref in RATE_LINES:
			row = lines[ref]
			if flt(row.rate):
				row.cumulative = flt(base * flt(row.rate) / 100, 2)
		# advance cannot be recovered beyond what was paid
		advance = flt(lines["F"].cumulative)
		if flt(lines["G"].rate) and lines["G"].cumulative > advance:
			lines["G"].cumulative = advance

	# ------------------------------------------------------------- calculate

	def calculate(self):
		for row in self.lines:
			row.cumulative = flt(row.cumulative, 2)
			row.this_period = flt(flt(row.cumulative) - flt(row.previous), 2)

		self.revised_contract_amount = flt(
			flt(self.subcontract_amount) + flt(self.approved_variations) + flt(self.other_adjustments), 2
		)
		for column in COLUMNS:
			summary = calculate_summary({row.ref: row.get(column) for row in self.lines}, self.vat_rate)
			for key, value in summary.items():
				self.set(f"{key}_{column}", value)

		self.in_words = (
			money_in_words(self.net_incl_vat_this_period, self.currency)
			if flt(self.net_incl_vat_this_period) > 0
			else ""
		)

	def calculate_back_charges(self):
		total = 0
		for row in self.get("back_charges") or []:
			row.currency = self.currency
			row.total = flt(flt(row.amount) + flt(row.vat), 2)
			total += row.total
		self.total_back_charges = flt(total, 2)

	# -------------------------------------------------------------- approval

	def set_approval(self):
		status = self.approval_status or "Draft"
		before = self.get_doc_before_save()
		old_status = (before.approval_status if before else None) or "Draft"
		if status == old_status and not self.is_new():
			return

		if status in ("Authorized", "Approved") and not set(APPROVER_ROLES) & set(frappe.get_roles()):
			frappe.throw(
				_("Only {0} can set the status to {1}.").format(", ".join(APPROVER_ROLES), _(status)),
				frappe.PermissionError,
			)
		if status == "Rejected" and not self.remarks:
			frappe.throw(_("Enter the reason for rejecting the certificate in Remarks."))

		field = APPROVAL_STEPS.get(status)
		if field:
			self.set(field, frappe.session.user)
		if status == "Approved":
			self.approved_on = nowdate()
		elif status in ("Draft", "Rejected"):
			self.approved_on = None
			self.approved_by = None

	def set_version(self):
		self.version = (
			cint(frappe.db.get_value("Payment Certificate", self.amended_from, "version")) + 1
			if self.amended_from
			else 1
		)

	# -------------------------------------------------------------- warnings

	def show_warnings(self):
		messages = []
		lines = {row.ref: row for row in self.lines}

		if flt(self.revised_contract_amount) and flt(self.gross_cumulative) > flt(
			self.revised_contract_amount
		):
			messages.append(
				_("Gross amount to date {0} is more than the revised contract amount {1}.").format(
					frappe.format(self.gross_cumulative, {"fieldtype": "Currency", "options": self.currency}),
					frappe.format(
						self.revised_contract_amount, {"fieldtype": "Currency", "options": self.currency}
					),
				)
			)
		if flt(lines["G"].cumulative) > flt(lines["F"].cumulative):
			messages.append(_("Recovery of Advance (G) is more than the Advance Payment (F)."))
		reduced = [
			f"{row.ref} {_(row.description)}"
			for row in self.lines
			if row.ref in ("A", "B", "C", "D") and flt(row.this_period) < 0
		]
		if reduced:
			messages.append(
				_("Cumulative is lower than the previous certificate for: {0}").format(", ".join(reduced))
			)
		if flt(self.net_incl_vat_this_period) < 0:
			messages.append(
				_("The amount for this period is negative (the subcontractor owes the difference).")
			)

		expired, expiring = [], []
		date = getdate(self.certificate_date or nowdate())
		notice = add_days(date, EXPIRY_NOTICE_DAYS)
		for key, label in SECURITIES:
			validity = self.get(f"{key}_validity")
			if not validity:
				continue
			if getdate(validity) < date:
				expired.append(f"{_(label)} ({frappe.format(validity, 'Date')})")
			elif getdate(validity) <= getdate(notice):
				expiring.append(f"{_(label)} ({frappe.format(validity, 'Date')})")
		if expired:
			messages.append(_("Expired: {0}").format(", ".join(expired)))
		if expiring:
			messages.append(
				_("Expiring within {0} days: {1}").format(EXPIRY_NOTICE_DAYS, ", ".join(expiring))
			)

		if self.application_no:
			duplicate = frappe.db.get_value(
				"Payment Certificate",
				{
					"supplier": self.supplier,
					"application_no": self.application_no,
					"docstatus": ["<", 2],
					"name": ["!=", self.name],
				},
				"name",
			)
			if duplicate:
				messages.append(
					_("Application No. {0} is already used on certificate {1}.").format(
						self.application_no, duplicate
					)
				)

		if messages:
			frappe.msgprint(
				"<ul><li>" + "</li><li>".join(messages) + "</li></ul>",
				title=_("Payment Certificate Warnings"),
				indicator="orange",
			)


@frappe.whitelist()
def get_previous(supplier=None, project=None, subcontract_work_order=None, certificate_date=None, name=None):
	"""Previous certificate and its cumulative figures, for the form."""
	frappe.has_permission("Payment Certificate", "read", throw=True)
	doc = frappe._dict(
		supplier=supplier,
		project=project,
		subcontract_work_order=subcontract_work_order,
		certificate_date=certificate_date,
	)
	certificate = previous_certificate(doc, exclude=name)
	return {"certificate": certificate, "values": previous_values(certificate)}


@frappe.whitelist()
def make_payment_certificate(source_name):
	"""New certificate from a Subcontract Work Order (button on the work order)."""
	frappe.has_permission("Payment Certificate", "create", throw=True)
	wo = frappe.get_doc("Subcontract Work Order", source_name)
	wo.check_permission("read")

	doc = frappe.new_doc("Payment Certificate")
	doc.update(
		{
			"supplier": wo.supplier,
			"subcontract_work_order": wo.name,
			"project": wo.project,
			"company": wo.company,
			"cost_center": wo.get("cost_center"),
			"subcontract_amount": flt(wo.get("total_currency")),
			"commencement_date": wo.get("start_date"),
		}
	)
	if wo.project:
		project = frappe.db.get_value(
			"Project", wo.project, ["project_name", "scope_of_work", "lpo_ref", "cost_center"], as_dict=True
		)
		if project:
			doc.project_name = project.project_name
			doc.scope_of_work = project.scope_of_work
			doc.client_po = project.lpo_ref
			doc.cost_center = doc.cost_center or project.cost_center
		budget = frappe.db.get_value("Project Budget", {"project": wo.project, "docstatus": 1}, "name")
		if budget:
			doc.project_budget = budget

	# carry over the securities and contract figures from the last certificate
	last = previous_certificate(doc)
	if last:
		keep = [f"{key}_{part}" for key, _label in SECURITIES for part in ("no", "validity")]
		keep += ["subcontract_type", "approved_variations", "other_adjustments", "duration", "vat_trn"]
		keep += ["payment_terms"]
		for field, value in frappe.db.get_value("Payment Certificate", last, keep, as_dict=True).items():
			if value:
				doc.set(field, value)
		rates = {
			r.ref: r.rate
			for r in frappe.get_all(
				"Payment Certificate Line",
				filters={"parent": last, "parenttype": "Payment Certificate"},
				fields=["ref", "rate"],
			)
		}
	else:
		rates = {}
	previous = previous_values(last)
	for ref, label in LINE_DEFS:
		doc.append(
			"lines",
			{
				"ref": ref,
				"description": label,
				"rate": flt(rates.get(ref)),
				"cumulative": previous.get(ref, 0),
				"previous": previous.get(ref, 0),
			},
		)
	return doc

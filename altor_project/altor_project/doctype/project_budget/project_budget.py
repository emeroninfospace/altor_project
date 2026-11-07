# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from altor_project.budget import calculate_budget, update_submitted_budget


class ProjectBudget(Document):
	def validate(self):
		self.validate_budget_lines()
		self.validate_duplicate_budget()
		self.validate_threshold()
		unbudgeted = calculate_budget(self)
		if not self.flags.ignore_budget_warnings:
			self.show_warnings(unbudgeted)

	def before_submit(self):
		missing = [row.category for row in self.budget_items if flt(row.budgeted_amount) <= 0]
		if missing:
			frappe.throw(
				_("Enter a Budgeted Amount for these Item Groups before submitting: {0}").format(
					", ".join(missing)
				),
				title=_("Budget Missing"),
			)

	def validate_budget_lines(self):
		if not self.budget_items:
			frappe.throw(_("Add at least one Item Group budget line."), title=_("Budget Missing"))

		seen = {}
		for row in self.budget_items:
			if not row.category:
				frappe.throw(_("Row #{0}: Item Group is mandatory.").format(row.idx))
			if row.category in seen:
				frappe.throw(
					_(
						"Row #{0}: Item Group {1} is already budgeted in row #{2}. Use one line per Item Group."
					).format(row.idx, frappe.bold(row.category), seen[row.category]),
					title=_("Duplicate Item Group"),
				)
			seen[row.category] = row.idx
			if flt(row.budgeted_amount) < 0:
				frappe.throw(_("Row #{0}: Budgeted Amount cannot be negative.").format(row.idx))

		# A parent and a child item group in the same budget is allowed (spend goes to the
		# deepest match) but is easy to do by mistake, so point it out.
		bounds = {
			g.name: (g.lft, g.rgt)
			for g in frappe.get_all(
				"Item Group", filters={"name": ["in", list(seen)]}, fields=["name", "lft", "rgt"]
			)
		}
		nested = []
		for child, cb in bounds.items():
			for parent, pb in bounds.items():
				if child != parent and pb[0] < cb[0] and pb[1] > cb[1]:
					nested.append(_("{0} is under {1}").format(child, parent))
		if nested and not self.flags.ignore_budget_warnings:
			frappe.msgprint(
				_(
					"Some Item Groups are nested: {0}. Spend is counted against the most specific Item Group only."
				).format("; ".join(nested)),
				title=_("Budget Warning"),
				indicator="orange",
			)

	def validate_duplicate_budget(self):
		existing = frappe.db.get_value(
			"Project Budget",
			{"project": self.project, "docstatus": 1, "name": ["!=", self.name]},
			"name",
		)
		if existing:
			frappe.throw(
				_(
					"Project {0} already has a submitted budget {1}. Cancel and amend it instead of creating a new one."
				).format(
					frappe.bold(self.project), frappe.utils.get_link_to_form("Project Budget", existing)
				),
				title=_("Budget Already Exists"),
			)

	def validate_threshold(self):
		if self.warning_threshold is None or self.warning_threshold == "":
			self.warning_threshold = 90
		if not 0 < flt(self.warning_threshold) <= 100:
			frappe.throw(_("Warning Threshold % must be between 1 and 100."))

	def show_warnings(self, unbudgeted):
		zero = [row.category for row in self.budget_items if flt(row.budgeted_amount) == 0]
		over_quoted = [
			_("{0} (budget {1} > quoted {2})").format(
				row.category,
				frappe.format(row.budgeted_amount, "Currency"),
				frappe.format(row.quoted_amount, "Currency"),
			)
			for row in self.budget_items
			if flt(row.quoted_amount) and flt(row.budgeted_amount) > flt(row.quoted_amount)
		]
		exceeded = [
			row for row in self.budget_items if row.budget_status == "Exceeded" and flt(row.budgeted_amount)
		]
		near = [row for row in self.budget_items if row.budget_status == "Warning"]

		messages = []
		if zero:
			messages.append(_("No budget entered yet for: {0}").format(", ".join(zero)))
		if over_quoted:
			messages.append(
				_("Budget (cost) is higher than the quoted selling value for: {0}").format(
					", ".join(over_quoted)
				)
			)
		if exceeded:
			messages.append(
				_("Budget exceeded for: {0}").format(
					", ".join(
						_("{0} ({1}% used)").format(r.category, round(flt(r.utilization_percentage), 1))
						for r in exceeded
					)
				)
			)
		if near:
			messages.append(
				_("Budget almost used for: {0}").format(
					", ".join(
						_("{0} ({1}% used)").format(r.category, round(flt(r.utilization_percentage), 1))
						for r in near
					)
				)
			)
		if unbudgeted:
			messages.append(
				_("Spend found on Item Groups without a budget line: {0}").format(
					", ".join(g if g != "__unbudgeted__" else _("(no item group)") for g in unbudgeted)
				)
			)
		if messages:
			frappe.msgprint(
				"<ul><li>" + "</li><li>".join(messages) + "</li></ul>",
				title=_("Budget Warnings"),
				indicator="red" if exceeded else "orange",
			)

	@frappe.whitelist()
	def refresh_actuals(self):
		"""Recalculate committed / actual figures (button on the form)."""
		self.check_permission("write" if self.docstatus == 0 else "read")
		if self.docstatus == 1:
			update_submitted_budget(self.name)
		elif self.docstatus == 0:
			self.save()
		return True


@frappe.whitelist()
def get_unbudgeted_spend(project, budget=None):
	"""Spend on item groups that are not part of the budget, for the form dashboard."""
	from altor_project.budget import UNBUDGETED, get_category_spend

	frappe.has_permission("Project Budget", "read", throw=True)
	categories = []
	if budget:
		categories = frappe.get_all(
			"Project Budget Item",
			filters={"parent": budget, "parenttype": "Project Budget"},
			pluck="category",
		)
	_per_category, unbudgeted = get_category_spend(project, categories)
	return [
		{
			"item_group": g if g != UNBUDGETED else _("(no item group)"),
			"utilized": flt(v["committed"]) + flt(v["direct_actual"]),
			"actual": flt(v["actual"]),
		}
		for g, v in unbudgeted.items()
		if flt(v["committed"]) or flt(v["actual"])
	]

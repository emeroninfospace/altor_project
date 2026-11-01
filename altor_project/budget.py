# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Item Group wise project budget: spend calculation and budget checks.

Amounts per budget line (Project Budget Item):

* Committed  - submitted Purchase Orders + Subcontract Work Orders
* Actual     - submitted Purchase Invoices + Subcontract Invoices
* Utilized   - Committed + Actual that is not against an order
               (direct invoices), so an order and its invoice are
               counted only once.

Spending is mapped to a budget line through the Item Group tree: an item in
"Cables" counts against a budget line for "Electrical" if "Cables" sits under
"Electrical". When several budget lines match, the deepest one wins.
"""

import frappe
from frappe import _
from frappe.utils import flt

UNBUDGETED = "__unbudgeted__"
DEFAULT_WARNING_THRESHOLD = 90


def get_active_budget(project):
	"""Return the name of the latest submitted Project Budget for a project."""
	if not project:
		return None
	rows = frappe.get_all(
		"Project Budget",
		filters={"project": project, "docstatus": 1},
		fields=["name"],
		order_by="posting_date desc, creation desc",
		limit=1,
	)
	return rows[0].name if rows else None


# ---------------------------------------------------------------------------
# Spend per item group
# ---------------------------------------------------------------------------


def _exclude_clause(alias, doctype, exclude):
	if exclude and exclude.get("doctype") == doctype and exclude.get("name"):
		return f" AND {alias}.name != %(exclude_name)s"
	return ""


def get_item_group_spend(project, exclude=None):
	"""Return {item_group: {committed, actual, direct_actual, pending_mr}} for a project.

	`exclude` = {"doctype": ..., "name": ...} leaves one document out (used
	while validating that document).
	"""
	values = {"project": project, "exclude_name": (exclude or {}).get("name")}
	spend = {}

	def add(rows, key):
		for row in rows:
			group = row.item_group or UNBUDGETED
			spend.setdefault(
				group, {"committed": 0.0, "actual": 0.0, "direct_actual": 0.0, "pending_mr": 0.0}
			)
			spend[group][key] += flt(row.amount)

	# Purchase Orders (committed)
	add(
		frappe.db.sql(
			f"""
			SELECT i.item_group, SUM(poi.base_net_amount) AS amount
			FROM `tabPurchase Order Item` poi
			INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
			LEFT JOIN `tabItem` i ON i.name = poi.item_code
			WHERE po.docstatus = 1 AND poi.project = %(project)s
			{_exclude_clause("po", "Purchase Order", exclude)}
			GROUP BY i.item_group
			""",
			values,
			as_dict=True,
		),
		"committed",
	)

	# Purchase Invoices (actual) and the part not against a Purchase Order
	pi_rows = frappe.db.sql(
		f"""
		SELECT i.item_group,
			SUM(pii.base_net_amount) AS amount,
			SUM(CASE WHEN IFNULL(pii.purchase_order, '') = '' THEN pii.base_net_amount ELSE 0 END) AS direct
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pinv ON pinv.name = pii.parent
		LEFT JOIN `tabItem` i ON i.name = pii.item_code
		WHERE pinv.docstatus = 1 AND pii.project = %(project)s
		{_exclude_clause("pinv", "Purchase Invoice", exclude)}
		GROUP BY i.item_group
		""",
		values,
		as_dict=True,
	)
	add(pi_rows, "actual")
	add([frappe._dict(item_group=r.item_group, amount=r.direct) for r in pi_rows], "direct_actual")

	# Subcontract Work Orders (committed)
	add(
		frappe.db.sql(
			f"""
			SELECT i.item_group, SUM(swi.amount) AS amount
			FROM `tabSubcontract Work Item` swi
			INNER JOIN `tabSubcontract Work Order` swo ON swo.name = swi.parent
			LEFT JOIN `tabItem` i ON i.name = swi.item_code
			WHERE swo.docstatus = 1 AND swo.project = %(project)s
			{_exclude_clause("swo", "Subcontract Work Order", exclude)}
			GROUP BY i.item_group
			""",
			values,
			as_dict=True,
		),
		"committed",
	)

	# Subcontract Invoices (actual) and the part not against a Work Order
	si_rows = frappe.db.sql(
		f"""
		SELECT i.item_group,
			SUM(sii.amount) AS amount,
			SUM(CASE WHEN IFNULL(sinv.subcontract_work_order, '') = '' THEN sii.amount ELSE 0 END) AS direct
		FROM `tabSubcontract Invoice Item` sii
		INNER JOIN `tabSubcontract Invoice` sinv ON sinv.name = sii.parent
		LEFT JOIN `tabItem` i ON i.name = sii.item_code
		WHERE sinv.docstatus = 1 AND sinv.project = %(project)s
		{_exclude_clause("sinv", "Subcontract Invoice", exclude)}
		GROUP BY i.item_group
		""",
		values,
		as_dict=True,
	)
	add(si_rows, "actual")
	add([frappe._dict(item_group=r.item_group, amount=r.direct) for r in si_rows], "direct_actual")

	# Material Requests not yet ordered (only used for MR checks)
	add(
		frappe.db.sql(
			f"""
			SELECT i.item_group,
				SUM(
					GREATEST(mri.stock_qty - IFNULL(mri.ordered_qty, 0), 0)
					/ IFNULL(NULLIF(mri.conversion_factor, 0), 1)
					* COALESCE(NULLIF(mri.rate, 0), NULLIF(i.last_purchase_rate, 0), i.valuation_rate, 0)
				) AS amount
			FROM `tabMaterial Request Item` mri
			INNER JOIN `tabMaterial Request` mr ON mr.name = mri.parent
			LEFT JOIN `tabItem` i ON i.name = mri.item_code
			WHERE mr.docstatus = 1
				AND mr.material_request_type = 'Purchase'
				AND mr.status NOT IN ('Stopped', 'Cancelled')
				AND COALESCE(NULLIF(mri.project, ''), mr.custom_project) = %(project)s
			{_exclude_clause("mr", "Material Request", exclude)}
			GROUP BY i.item_group
			""",
			values,
			as_dict=True,
		),
		"pending_mr",
	)

	return spend


# ---------------------------------------------------------------------------
# Item group tree helpers
# ---------------------------------------------------------------------------


def _get_group_bounds(groups):
	groups = [g for g in set(groups) if g and g != UNBUDGETED]
	if not groups:
		return {}
	rows = frappe.get_all("Item Group", filters={"name": ["in", groups]}, fields=["name", "lft", "rgt"])
	return {r.name: (r.lft, r.rgt) for r in rows}


class CategoryMapper:
	"""Maps any item group to the deepest budget category that contains it."""

	def __init__(self, categories):
		self.categories = [c for c in categories if c]
		self.bounds = _get_group_bounds(self.categories)
		self._cache = {}

	def resolve(self, item_group, bounds=None):
		if not item_group or item_group == UNBUDGETED:
			return None
		if item_group in self._cache:
			return self._cache[item_group]
		if item_group in self.categories:
			self._cache[item_group] = item_group
			return item_group
		bound = (bounds or {}).get(item_group)
		match, match_lft = None, -1
		if bound:
			for cat in self.categories:
				cat_bound = self.bounds.get(cat)
				if (
					cat_bound
					and cat_bound[0] <= bound[0]
					and cat_bound[1] >= bound[1]
					and cat_bound[0] > match_lft
				):
					match, match_lft = cat, cat_bound[0]
		self._cache[item_group] = match
		return match


def get_category_spend(project, categories, exclude=None):
	"""Roll item group spend up to budget categories.

	Returns (per_category, unbudgeted) where unbudgeted holds spend on item
	groups that have no budget line.
	"""
	spend = get_item_group_spend(project, exclude=exclude)
	mapper = CategoryMapper(categories)
	bounds = _get_group_bounds(spend.keys())
	empty = lambda: {"committed": 0.0, "actual": 0.0, "direct_actual": 0.0, "pending_mr": 0.0}  # noqa: E731
	per_category = {c: empty() for c in categories if c}
	unbudgeted = {}
	for group, amounts in spend.items():
		cat = mapper.resolve(group, bounds)
		target = per_category[cat] if cat else unbudgeted.setdefault(group, empty())
		for key, val in amounts.items():
			target[key] += val
	return per_category, unbudgeted


def get_status(utilization, threshold):
	if utilization > 100:
		return "Exceeded"
	if utilization >= flt(threshold or DEFAULT_WARNING_THRESHOLD):
		return "Warning"
	return "Within Budget"


# ---------------------------------------------------------------------------
# Updating a Project Budget
# ---------------------------------------------------------------------------


def calculate_budget(doc):
	"""Fill committed / actual / utilization on a Project Budget document (in memory)."""
	categories = [row.category for row in doc.budget_items]
	per_category, unbudgeted = get_category_spend(doc.project, categories) if doc.project else ({}, {})
	threshold = flt(doc.warning_threshold) or DEFAULT_WARNING_THRESHOLD

	totals = {"budget": 0.0, "committed": 0.0, "actual": 0.0, "utilized": 0.0}
	for row in doc.budget_items:
		amounts = per_category.get(row.category) or {}
		row.committed_amount = flt(amounts.get("committed"))
		row.actual_amount = flt(amounts.get("actual"))
		row.utilized_amount = row.committed_amount + flt(amounts.get("direct_actual"))
		budget = flt(row.budgeted_amount)
		row.variance = budget - row.utilized_amount
		row.variance_percentage = (row.variance / budget * 100) if budget else 0
		row.utilization_percentage = (
			(row.utilized_amount / budget * 100) if budget else (100 if row.utilized_amount else 0)
		)
		row.budget_status = get_status(
			row.utilization_percentage if budget else (101 if row.utilized_amount else 0), threshold
		)

		totals["budget"] += budget
		totals["committed"] += row.committed_amount
		totals["actual"] += row.actual_amount
		totals["utilized"] += row.utilized_amount

	doc.total_estimated_cost = totals["budget"]
	doc.total_committed_cost = totals["committed"]
	doc.total_actual_cost = totals["actual"]
	doc.total_utilized_cost = totals["utilized"]
	doc.variance = totals["budget"] - totals["utilized"]
	doc.variance_percentage = (doc.variance / totals["budget"] * 100) if totals["budget"] else 0
	doc.utilization_percentage = (totals["utilized"] / totals["budget"] * 100) if totals["budget"] else 0
	doc.unbudgeted_amount = sum(flt(v["committed"]) + flt(v["direct_actual"]) for v in unbudgeted.values())
	# Overall status is the worst of the total and the individual item group lines.
	line_statuses = {row.budget_status for row in doc.budget_items}
	overall = get_status(doc.utilization_percentage, threshold) if totals["budget"] else ""
	if "Exceeded" in line_statuses or overall == "Exceeded":
		doc.budget_status = "Exceeded"
	elif "Warning" in line_statuses or overall == "Warning":
		doc.budget_status = "Warning"
	else:
		doc.budget_status = overall
	doc.last_updated_on = frappe.utils.now_datetime()
	return unbudgeted


ROW_FIELDS = (
	"committed_amount",
	"actual_amount",
	"utilized_amount",
	"variance",
	"variance_percentage",
	"utilization_percentage",
	"budget_status",
)
PARENT_FIELDS = (
	"total_estimated_cost",
	"total_committed_cost",
	"total_actual_cost",
	"total_utilized_cost",
	"variance",
	"variance_percentage",
	"utilization_percentage",
	"unbudgeted_amount",
	"budget_status",
	"last_updated_on",
)


def update_submitted_budget(budget_name):
	"""Recalculate a submitted Project Budget and write the figures to the database."""
	doc = frappe.get_doc("Project Budget", budget_name)
	calculate_budget(doc)
	for row in doc.budget_items:
		frappe.db.set_value(
			"Project Budget Item", row.name, {f: row.get(f) for f in ROW_FIELDS}, update_modified=False
		)
	frappe.db.set_value(
		"Project Budget", doc.name, {f: doc.get(f) for f in PARENT_FIELDS}, update_modified=False
	)
	return doc


def update_project_budget(project):
	budget = get_active_budget(project)
	if budget:
		update_submitted_budget(budget)


def _projects_of(doc):
	projects = set()
	if doc.get("project"):
		projects.add(doc.project)
	if doc.get("custom_project"):
		projects.add(doc.custom_project)
	for row in doc.get("items") or []:
		if row.get("project"):
			projects.add(row.project)
	return projects


def on_transaction_change(doc, method=None):
	"""doc_event: keep budget figures current when spend documents are submitted / cancelled."""
	for project in _projects_of(doc):
		try:
			update_project_budget(project)
		except Exception:
			frappe.log_error(title=f"Project Budget update failed for {project}")


# ---------------------------------------------------------------------------
# Budget checks on Material Request / Purchase Order
# ---------------------------------------------------------------------------

CHECK_CONFIG = {
	"Material Request": ("applicable_on_material_request", "action_if_annual_budget_exceeded_on_mr"),
	"Purchase Order": ("applicable_on_purchase_order", "action_if_annual_budget_exceeded_on_po"),
}


def _doc_amounts_by_group(doc, project):
	"""Amount per item group of the rows of `doc` that belong to `project`."""
	amounts = {}
	item_codes = [r.item_code for r in doc.get("items") or [] if r.get("item_code")]
	item_info = {}
	if item_codes:
		for it in frappe.get_all(
			"Item",
			filters={"name": ["in", list(set(item_codes))]},
			fields=["name", "item_group", "last_purchase_rate", "valuation_rate"],
		):
			item_info[it.name] = it

	for row in doc.get("items") or []:
		row_project = row.get("project") or doc.get("custom_project") or doc.get("project")
		if row_project != project or not row.get("item_code"):
			continue
		info = item_info.get(row.item_code) or frappe._dict()
		group = row.get("item_group") or info.get("item_group") or UNBUDGETED
		if doc.doctype == "Purchase Order":
			amount = flt(row.get("base_net_amount")) or flt(row.get("base_amount")) or flt(row.get("amount"))
		else:
			rate = (
				flt(row.get("rate")) or flt(info.get("last_purchase_rate")) or flt(info.get("valuation_rate"))
			)
			amount = flt(row.get("amount")) or flt(row.get("qty")) * rate
		amounts[group] = amounts.get(group, 0.0) + amount
	return amounts


def validate_budget(doc, method=None):
	"""doc_event (validate) for Material Request and Purchase Order."""
	if doc.doctype not in CHECK_CONFIG:
		return
	if doc.doctype == "Material Request" and doc.get("material_request_type") not in (None, "", "Purchase"):
		return

	applicable_field, action_field = CHECK_CONFIG[doc.doctype]
	for project in _projects_of(doc):
		budget_name = get_active_budget(project)
		if not budget_name:
			continue
		budget = frappe.get_doc("Project Budget", budget_name)
		if not budget.get(applicable_field):
			continue
		action = budget.get(action_field) or "Warn"
		if action == "Ignore":
			continue
		_check_against_budget(doc, project, budget, action)


def _check_against_budget(doc, project, budget, action):
	this_doc = _doc_amounts_by_group(doc, project)
	if not this_doc:
		return

	categories = [r.category for r in budget.budget_items]
	budget_by_cat = {}
	for r in budget.budget_items:
		budget_by_cat[r.category] = budget_by_cat.get(r.category, 0.0) + flt(r.budgeted_amount)

	exclude = {"doctype": doc.doctype, "name": doc.name} if not doc.is_new() else None
	per_category, _unused = get_category_spend(project, categories, exclude=exclude)

	mapper = CategoryMapper(categories)
	bounds = _get_group_bounds(this_doc.keys())
	this_by_cat, not_in_budget = {}, []
	for group, amount in this_doc.items():
		cat = mapper.resolve(group, bounds)
		if cat:
			this_by_cat[cat] = this_by_cat.get(cat, 0.0) + amount
		else:
			not_in_budget.append(group if group != UNBUDGETED else _("(no item group)"))

	threshold = flt(budget.warning_threshold) or DEFAULT_WARNING_THRESHOLD
	exceeded, near = [], []
	for cat, amount in this_by_cat.items():
		used = per_category.get(cat) or {}
		existing = flt(used.get("committed")) + flt(used.get("direct_actual"))
		if doc.doctype == "Material Request":
			existing += flt(used.get("pending_mr"))
		total = existing + amount
		limit = budget_by_cat.get(cat, 0.0)
		line = _("<b>{0}</b>: budget {1}, already used {2}, this {3} {4}, total {5}").format(
			cat,
			frappe.format(limit, "Currency"),
			frappe.format(existing, "Currency"),
			_(doc.doctype),
			frappe.format(amount, "Currency"),
			frappe.format(total, "Currency"),
		)
		if total > limit + 0.005:
			exceeded.append(
				line + _(" &rarr; exceeds by {0}").format(frappe.format(total - limit, "Currency"))
			)
		elif limit and total / limit * 100 >= threshold:
			near.append(line + _(" &rarr; {0}% of budget used").format(round(total / limit * 100, 1)))

	link = frappe.utils.get_link_to_form("Project Budget", budget.name)
	if exceeded:
		msg = _("Item Group budget exceeded for Project {0} ({1}):").format(project, link)
		msg += "<ul><li>" + "</li><li>".join(exceeded) + "</li></ul>"
		if action == "Stop":
			frappe.throw(msg, title=_("Budget Exceeded"))
		frappe.msgprint(msg, title=_("Budget Exceeded"), indicator="red")
	if near:
		msg = _("Item Group budget almost used for Project {0} ({1}):").format(project, link)
		msg += "<ul><li>" + "</li><li>".join(near) + "</li></ul>"
		frappe.msgprint(msg, title=_("Budget Warning"), indicator="orange")
	if not_in_budget:
		frappe.msgprint(
			_("These Item Groups have no budget line in {0} for Project {1}: {2}").format(
				link, project, ", ".join(sorted(set(not_in_budget)))
			),
			title=_("Budget Warning"),
			indicator="orange",
		)


def refresh_all_budgets():
	"""Daily job: recalculate every submitted Project Budget."""
	for name in frappe.get_all("Project Budget", filters={"docstatus": 1}, pluck="name"):
		try:
			update_submitted_budget(name)
		except Exception:
			frappe.log_error(title=f"Project Budget refresh failed for {name}")

"""Connections (linked documents) added to ERPNext / HRMS forms.

Each function receives the dashboard data built by ERPNext/HRMS and extends it,
so the standard connections stay as they are.
"""

from frappe import _


def _add(data, label, items, fieldnames=None, internal=None):
	data.setdefault("transactions", [])
	data.setdefault("non_standard_fieldnames", {})
	data.setdefault("internal_links", {})
	existing = {i for group in data["transactions"] for i in group.get("items", [])}
	items = [i for i in items if i not in existing]
	if items:
		group = next((g for g in data["transactions"] if g.get("label") == label), None)
		if group:
			group["items"] = group.get("items", []) + items
		else:
			data["transactions"].append({"label": label, "items": items})
	data["non_standard_fieldnames"].update(fieldnames or {})
	data["internal_links"].update(internal or {})
	return data


def project(data):
	_add(data, _("Budget & Manpower"), ["Project Budget", "Manpower Entry", "Expense Entry"])
	_add(data, _("Planning"), ["Project Schedule"])
	_add(data, _("Subcontract"), ["Subcontract Work Order", "Subcontract Invoice"])
	_add(data, _("Selling"), ["Quotation"], internal={"Quotation": "quotation"})
	# Material Requests made from a project carry it in the header field custom_project
	data["non_standard_fieldnames"].setdefault("Material Request", "custom_project")
	return data


def quotation(data):
	# keep ERPNext's Sales Order / Auto Repeat links and add the Altor documents
	data.setdefault("fieldname", "prevdoc_docname")
	_add(
		data,
		_("Selling"),
		["Proforma Invoice", "Sales Invoice"],
		fieldnames={"Proforma Invoice": "quotation", "Sales Invoice": "custom_quotation"},
	)
	_add(data, _("Projects"), ["Project"], fieldnames={"Project": "quotation"})
	return data


def lead(data):
	return _add(data, _("Site Visit"), ["Site Visit"], fieldnames={"Site Visit": "lead"})


def supplier(data):
	# Manpower Entry: agency on the worker rows
	return _add(
		data, _("Subcontract & Manpower"), ["Subcontract Work Order", "Subcontract Invoice", "Manpower Entry"]
	)


def employee(data):
	return _add(
		data,
		_("Projects & Manpower"),
		["Manpower Entry", "Site Visit", "Expense Entry"],
		fieldnames={
			"Manpower Entry": "employee",
			"Site Visit": "visited_by",
			"Expense Entry": "employee_name",
		},
	)

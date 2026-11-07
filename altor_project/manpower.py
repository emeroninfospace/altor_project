# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Hourly cost rates for own staff and outsourced manpower.

Order of preference for the hourly rate of a worker:

1. Hourly Cost Rate on the Employee
2. Outsourced: agency rate from Altor Settings (supplier + designation,
   then the supplier's default row without designation)
3. Own staff: CTC / 12 / working days per month / working hours per day

OT rate: OT Hourly Rate on the Employee, then the agency OT rate, then
hourly rate x OT Multiplier.
"""

import frappe
from frappe import _
from frappe.utils import flt

OWN = "Own Staff"
OUTSOURCED = "Outsourced"


def get_settings():
	"""Altor Settings values needed for costing, cached per request."""
	if not getattr(frappe.local, "altor_manpower_settings", None):
		s = frappe.get_cached_doc("Altor Settings")
		rates = {}
		for row in s.get("manpower_rates") or []:
			rates[(row.supplier, row.designation or "")] = (flt(row.hourly_rate), flt(row.ot_hourly_rate))
		frappe.local.altor_manpower_settings = frappe._dict(
			item_group=s.get("default_manpower_item_group"),
			ot_multiplier=flt(s.get("ot_multiplier")) or 1.25,
			days=flt(s.get("working_days_per_month")) or 26,
			hours=flt(s.get("working_hours_per_day")) or 8,
			rates=rates,
		)
	return frappe.local.altor_manpower_settings


def _employee_fields():
	meta = frappe.get_meta("Employee")
	fields = ["name", "employee_name", "designation", "status", "company"]
	for f in (
		"custom_is_outsourced",
		"custom_manpower_supplier",
		"custom_hourly_cost_rate",
		"custom_ot_hourly_rate",
		"ctc",
	):
		if meta.has_field(f):
			fields.append(f)
	return fields


def get_employees(names):
	names = [n for n in set(names) if n]
	if not names:
		return {}
	return {
		e.name: e
		for e in frappe.get_all("Employee", filters={"name": ["in", names]}, fields=_employee_fields())
	}


def resolve_rates(worker_type, supplier=None, designation=None, employee=None):
	"""Return (hourly_rate, ot_hourly_rate) for a worker. `employee` is a dict from get_employees."""
	s = get_settings()
	hourly, ot = 0.0, 0.0
	if employee:
		hourly = flt(employee.get("custom_hourly_cost_rate"))
		ot = flt(employee.get("custom_ot_hourly_rate"))
	if worker_type == OUTSOURCED and supplier:
		agency = s.rates.get((supplier, designation or "")) or s.rates.get((supplier, ""))
		if agency:
			hourly = hourly or agency[0]
			ot = ot or agency[1]
	if not hourly and worker_type == OWN and employee and flt(employee.get("ctc")):
		hourly = flt(employee.ctc) / 12 / s.days / s.hours
	if not ot and hourly:
		ot = hourly * s.ot_multiplier
	return flt(hourly, 2), flt(ot, 2)


@frappe.whitelist()
def get_worker_details(employee=None, worker_type=None, supplier=None, designation=None):
	"""Used by the Manpower Entry form to fill a row."""
	frappe.has_permission("Manpower Entry", "write", throw=True)
	emp = get_employees([employee]).get(employee) if employee else None
	if emp:
		worker_type = OUTSOURCED if emp.get("custom_is_outsourced") else OWN
		supplier = emp.get("custom_manpower_supplier") if worker_type == OUTSOURCED else None
		designation = emp.designation or designation
	hourly, ot = resolve_rates(worker_type or OWN, supplier, designation, emp)
	return {
		"worker_type": worker_type or OWN,
		"supplier": supplier,
		"designation": designation,
		"hourly_rate": hourly,
		"ot_hourly_rate": ot,
		"employee_status": emp.status if emp else None,
	}


@frappe.whitelist()
def get_default_item_group():
	frappe.has_permission("Manpower Entry", "read", throw=True)
	return get_settings().item_group


def missing_rate_message(rows):
	return _(
		"No hourly rate found for rows {0}. Set the Hourly Cost Rate on the Employee or an agency rate in Altor Settings > Outsourced Manpower Rates."
	).format(", ".join(f"#{r.idx}" for r in rows))

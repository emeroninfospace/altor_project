# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Fill in defaults of Single (settings) doctypes.

Frappe does not apply the `default` of a field added to a Single doctype after the
settings were first saved: the field reads as empty / 0 until someone saves the form.
That silently switched off e.g. "Number Documents by Division" and "Skip Holidays for
Crews". This sets the default of every field that has never been stored, and leaves
values that were saved (even 0 / empty on purpose) untouched.
"""

import frappe

NO_VALUE_TYPES = (
	"Section Break",
	"Column Break",
	"Tab Break",
	"HTML",
	"Button",
	"Table",
	"Table MultiSelect",
	"Heading",
)


def apply_single_defaults(doctype="Altor Settings"):
	if not frappe.db.exists("DocType", doctype):
		return []
	stored = set(frappe.db.sql_list("SELECT field FROM `tabSingles` WHERE doctype = %s", doctype))
	applied = []
	for df in frappe.get_meta(doctype).fields:
		if df.fieldtype in NO_VALUE_TYPES or df.default in (None, "") or df.fieldname in stored:
			continue
		frappe.db.set_single_value(doctype, df.fieldname, df.default)
		applied.append(df.fieldname)
	if applied:
		frappe.clear_document_cache(doctype, doctype)
	return applied

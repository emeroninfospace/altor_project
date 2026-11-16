# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Hide Frappe / ERPNext promotional content from the workspaces.

* URL shortcuts to Frappe School courses, Frappe Cloud marketplace and Frappe / ERPNext docs
  ("Learn Project Management", "Learn Accounting", "Browse Apps", ...)
* the Frappe onboarding panels ("Let's set up ...") placed on standard workspaces

ERPNext and HRMS ship these workspaces, and an update can bring the links back, so this runs
after every migrate (hooks.after_migrate). Shortcuts that open pages of this site are kept.
"""

import json

import frappe

FRAPPE_HOSTS = (
	"frappe.io",
	"frappe.school",
	"frappecloud.com",
	"frappeframework.com",
	"erpnext.com",
	"erpnext.org",
	"frappehr.com",
)


def is_frappe_link(url):
	url = (url or "").lower()
	return url.startswith(("http://", "https://")) and any(host in url for host in FRAPPE_HOSTS)


def hide_frappe_links():
	"""Remove Frappe learning / marketplace shortcuts and onboarding panels from all workspaces."""
	changed = []
	for ws in frappe.get_all("Workspace", fields=["name", "content"]):
		labels = {
			s.label
			for s in frappe.get_all(
				"Workspace Shortcut",
				filters={"parent": ws.name, "parenttype": "Workspace", "type": "URL"},
				fields=["label", "url"],
			)
			if is_frappe_link(s.url)
		}
		try:
			blocks = json.loads(ws.content or "[]")
		except ValueError:
			continue
		kept = [
			b
			for b in blocks
			if b.get("type") != "onboarding"
			and not (b.get("type") == "shortcut" and (b.get("data") or {}).get("shortcut_name") in labels)
		]
		if not labels and len(kept) == len(blocks):
			continue
		if labels:
			frappe.db.delete(
				"Workspace Shortcut",
				{"parent": ws.name, "parenttype": "Workspace", "label": ["in", list(labels)]},
			)
		frappe.db.set_value("Workspace", ws.name, "content", json.dumps(kept), update_modified=False)
		changed.append(ws.name)
	if changed:
		frappe.clear_cache()
	return changed

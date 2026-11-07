// Copyright (c) 2026, emeron and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site Visit", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.lead) {
			frm.add_custom_button(__("Quotation"), () => {
				frappe.model.open_mapped_doc({
					method: "erpnext.crm.doctype.lead.lead.make_quotation",
					source_name: frm.doc.lead,
				});
			}, __("Create"));
		}
	},

	lead(frm) {
		if (frm.doc.lead) {
			frappe.db.get_value("Lead", frm.doc.lead, "lead_name", function (r) {
				if (r && r.lead_name) {
					frm.set_value("lead_name", r.lead_name);
				}
			});
		} else {
			frm.set_value("lead_name", "");
		}
	},
});

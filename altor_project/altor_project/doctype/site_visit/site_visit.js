// Copyright (c) 2026, emeron and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site Visit", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Bill of Quantity"), () => {
				make_bill_of_quantity(frm);
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

function make_bill_of_quantity(frm) {
	frappe.model.with_doctype("Bill of Quantity", function () {
		let doc = frappe.model.get_new_doc("Bill of Quantity");
		doc.site_visit = frm.doc.name;

		if (!frm.doc.lead) {
			frappe.set_route("Form", "Bill of Quantity", doc.name);
			return;
		}

		frappe.db.get_value("Customer", { lead_name: frm.doc.lead }, "name", function (r) {
			if (r && r.name) {
				doc.party_type = "Customer";
				doc.party_name = r.name;
			} else {
				doc.party_type = "Lead";
				doc.party_name = frm.doc.lead;
			}
			frappe.set_route("Form", "Bill of Quantity", doc.name);
		});
	});
}

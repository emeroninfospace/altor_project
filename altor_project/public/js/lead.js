const LEAD_STATUS_COLORS = {
    "Lead": "gray",
    "Open": "green",
    "Replied": "green",
    "Opportunity": "blue",
    "Interested": "blue",
    "Converted": "purple",
    "Do Not Contact": "red",
    "Site Visit Completed": "orange"
};

frappe.ui.form.on("Lead", {
    refresh(frm) {
        const color = LEAD_STATUS_COLORS[frm.doc.status];
        if (color) {
            frm.page.set_indicator(__(frm.doc.status), color);
        }

        if (!frm.is_new() && frm.doc.__onload && !frm.doc.__onload.is_customer) {
            frm.add_custom_button(__("Site Visit"), () => {
                frappe.model.with_doctype("Site Visit", function () {
                    let doc = frappe.model.get_new_doc("Site Visit");
                    doc.lead = frm.doc.name;
                    doc.lead_name = frm.doc.lead_name || frm.doc.company_name;
                    frappe.set_route("Form", "Site Visit", doc.name);
                });
            }, __("Create"));

        }

        setTimeout(() => {
            frm.page.remove_inner_button(__("Opportunity"), __("Create"));
            frm.page.remove_inner_button(__("Prospect"), __("Create"));
            frm.page.wrapper.find('button:contains("Action")').hide();
        }, 100);
    }
});

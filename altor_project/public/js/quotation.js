frappe.ui.form.on("Quotation", {
    refresh(frm) {
        if (!frm.is_new() && frm.doc.docstatus === 1) {

            frm.add_custom_button(
                __("Proforma Invoice"),
                () => {
                    frappe.call({
                        method: "altor_project.altor_project.doctype.proforma_invoice.proforma_invoice.make_proforma_invoice",
                        args: {
                            quotation: frm.doc.name
                        },
                        callback(r) {
                            if (r.message) {
                                frappe.model.sync(r.message);
                                frappe.set_route(
                                    "Form",
                                    r.message.doctype,
                                    r.message.name
                                );
                            }
                        }
                    });
                },
                __("Create")
            );

            frm.add_custom_button(
                __("Sales Invoice"),
                () => {
                    frappe.model.open_mapped_doc({
                        method: "altor_project.events.quotation.make_sales_invoice",
                        frm: frm
                    });
                },
                __("Create")
            );
        }

        if (
            frm.doc.docstatus === 1 &&
            frm.doc.status !== "Closed" &&
            frm.doc.status !== "Lost"
        ) {
            frm.add_custom_button(
                __("Project"),
                function () {
                    frappe.model.open_mapped_doc({
                        method: "altor_project.events.quotation.make_project",
                        frm: frm
                    });
                },
                __("Create")
            );
        }
    }
});

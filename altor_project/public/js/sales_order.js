frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        // Altor Settings > Sales Order Only from Quotation: the server refuses lines without a quotation
        if (frm.doc.docstatus === 0 && !(frm.doc.items || []).some((row) => row.prevdoc_docname)) {
            frm.set_intro(
                __("Make Sales Orders from a submitted Quotation: Quotation > Create > Sales Order, or Get Items From > Quotation."),
                "orange"
            );
            frm.altor_quotation_intro = true;
        } else if (frm.altor_quotation_intro) {
            frm.set_intro("");
            frm.altor_quotation_intro = false;
        }

        if (frm.doc.docstatus === 1 && !["Closed", "On Hold"].includes(frm.doc.status)) {
            frm.add_custom_button(
                __("Proforma Invoice"),
                () => {
                    frappe.model.open_mapped_doc({
                        method: "altor_project.altor_project.doctype.proforma_invoice.proforma_invoice.make_proforma_invoice_from_sales_order",
                        frm: frm,
                    });
                },
                __("Create")
            );
        }
    },
});

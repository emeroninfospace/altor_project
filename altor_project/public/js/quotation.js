frappe.ui.form.on("Quotation", {
    refresh(frm) {
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

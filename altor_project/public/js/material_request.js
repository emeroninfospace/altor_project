frappe.ui.form.on("Material Request", {

    custom_project: function (frm) {
        sync_project_to_items(frm);
    },

});

frappe.ui.form.on("Material Request Item", {
    items_add: function (frm, cdt, cdn) {
        if (frm.doc.custom_project) {
            frappe.model.set_value(
                cdt,
                cdn,
                "project",
                frm.doc.custom_project
            );
        }
    }
});

function sync_project_to_items(frm) {
    const project = frm.doc.custom_project || null;

    (frm.doc.items || []).forEach(row => {
        if (row.project !== project) {
            frappe.model.set_value(
                row.doctype,
                row.name,
                "project",
                project
            );
        }
    });
}

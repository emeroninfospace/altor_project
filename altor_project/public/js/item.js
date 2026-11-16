// Altor: a "Project Asset" item (scaffolding materials, equipment issued to projects) is an ERPNext
// fixed asset item bought in quantity: one grouped Asset per GRN, created automatically.
frappe.ui.form.on("Item", {
    custom_is_project_asset(frm) {
        if (!frm.doc.custom_is_project_asset) return;
        frm.set_value("is_stock_item", 0);
        frm.set_value("is_fixed_asset", 1);
        if (frm.fields_dict.is_grouped_asset) frm.set_value("is_grouped_asset", 1);
        if (frm.fields_dict.auto_create_assets) frm.set_value("auto_create_assets", 1);
        frappe.show_alert({ message: __("Fixed asset item: choose its Asset Category (accounts and depreciation)."), indicator: "blue" });
    },
});

frappe.listview_settings["Manpower Entry"] = {
    add_fields: ["total_cost", "outsourced_cost", "docstatus"],
    get_indicator(doc) {
        if (doc.docstatus === 0) return [__("Draft"), "red", "docstatus,=,0"];
        if (doc.docstatus === 2) return [__("Cancelled"), "gray", "docstatus,=,2"];
        return flt(doc.outsourced_cost) ? [__("Outsourced"), "orange", "docstatus,=,1"] : [__("Own Staff"), "green", "docstatus,=,1"];
    }
};

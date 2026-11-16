frappe.listview_settings["Asset Allocation"] = {
    add_fields: ["status", "docstatus"],
    get_indicator(doc) {
        const colours = { Draft: "gray", Allocated: "blue", "Partly Returned": "orange", Returned: "green", Cancelled: "red" };
        return [__(doc.status), colours[doc.status] || "gray", `status,=,${doc.status}`];
    },
};

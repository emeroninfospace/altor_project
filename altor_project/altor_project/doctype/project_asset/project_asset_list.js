frappe.listview_settings["Project Asset"] = {
    add_fields: ["status", "available_qty", "allocated_qty", "disabled"],
    get_indicator(doc) {
        if (doc.disabled) return [__("Disabled"), "gray", "disabled,=,1"];
        const colours = { Available: "green", "Partly Allocated": "blue", "Fully Allocated": "orange", "Written Off": "red" };
        return [__(doc.status), colours[doc.status] || "gray", `status,=,${doc.status}`];
    },
};

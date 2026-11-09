frappe.listview_settings["Payment Certificate"] = {
    add_fields: ["approval_status", "docstatus", "net_incl_vat_this_period", "currency"],
    get_indicator(doc) {
        if (doc.docstatus === 1) return [__("Certified"), "green", "docstatus,=,1"];
        if (doc.docstatus === 2) return [__("Cancelled"), "red", "docstatus,=,2"];
        const colours = {
            Draft: "gray", Initiated: "blue", Reviewed: "blue", Checked: "purple",
            Authorized: "orange", Approved: "green", Rejected: "red",
        };
        const status = doc.approval_status || "Draft";
        return [__(status), colours[status] || "gray", `approval_status,=,${status}`];
    },
};

frappe.listview_settings["Lead"] = {
    get_indicator: function (doc) {
        const statusMap = {
            "Lead": "gray",
            "Open": "green",
            "Replied": "green",
            "Opportunity": "blue",
            "Interested": "blue",
            "Converted": "purple",
            "Do Not Contact": "red",
            "Site Visit Completed": "orange",
            "Bill of Quantity Completed": "yellow"
        };
        const color = statusMap[doc.status] || "gray";
        return [__(doc.status), color, "status,=," + doc.status];
    }
};

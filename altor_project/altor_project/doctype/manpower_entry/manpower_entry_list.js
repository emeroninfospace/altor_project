frappe.listview_settings["Manpower Entry"] = {
    add_fields: ["total_cost", "outsourced_cost", "docstatus", "auto_created"],
    get_indicator(doc) {
        if (doc.docstatus === 0) return [doc.auto_created ? __("Auto Draft") : __("Draft"), "red", "docstatus,=,0"];
        if (doc.docstatus === 2) return [__("Cancelled"), "gray", "docstatus,=,2"];
        return flt(doc.outsourced_cost) ? [__("Outsourced"), "orange", "docstatus,=,1"] : [__("Own Staff"), "green", "docstatus,=,1"];
    },
    onload(listview) {
        if (!frappe.model.can_create("Manpower Entry")) return;
        listview.page.add_inner_button(__("Create from Attendance"), () => {
            const d = new frappe.ui.Dialog({
                title: __("Create Manpower Entries"),
                fields: [
                    { fieldname: "date", fieldtype: "Date", label: __("Date"), reqd: 1, default: frappe.datetime.add_days(frappe.datetime.get_today(), -1) },
                    { fieldname: "source", fieldtype: "Select", label: __("Hours Source"), options: "Attendance\nEmployee Checkin", default: "Attendance" },
                    { fieldname: "submit", fieldtype: "Check", label: __("Submit Automatically") },
                    {
                        fieldname: "help", fieldtype: "HTML",
                        options: `<div class="text-muted small">${__("One entry per project: employees from attendance / checkins (by their Assigned Project) plus each project's Daily Manpower Crew. Employees and crews already booked that day are skipped.")}</div>`
                    }
                ],
                primary_action_label: __("Create"),
                primary_action(values) {
                    d.hide();
                    frappe.call({
                        method: "altor_project.manpower_automation.create_manpower_entries",
                        args: values,
                        freeze: true,
                        freeze_message: __("Creating Manpower Entries..."),
                        callback(r) {
                            const res = r.message || {};
                            const list = (items) => items.length ? `<ul>${items.map((i) => `<li>${frappe.utils.escape_html(i)}</li>`).join("")}</ul>` : "";
                            frappe.msgprint({
                                title: __("Manpower Entries for {0}", [frappe.datetime.str_to_user(res.date)]),
                                indicator: (res.errors || []).length ? "orange" : "green",
                                message: `<p>${__("Created")}: <b>${(res.created || []).length}</b></p>${list(res.created || [])}
                                    ${(res.skipped || []).length ? `<p>${__("Skipped")}:</p>${list(res.skipped)}` : ""}
                                    ${(res.errors || []).length ? `<p>${__("Errors")}:</p>${list(res.errors)}` : ""}`
                            });
                            listview.refresh();
                        }
                    });
                }
            });
            d.show();
        });
    }
};

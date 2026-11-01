// Copyright (c) 2026, emeron and contributors
// For license information, please see license.txt

frappe.ui.form.on("Expense Entry", {
    refresh: function(frm) {

        frm.set_query("account", "items", function() {
            return {
                filters: {
                    is_group     : 0,
                    company      : frm.doc.company,
                   
                    
                }
            };
        });

        frm.set_query("account_from", "items", function() {
            return {
                filters: {
                    is_group     : 0,
                    company      : frm.doc.company,
                    account_type : ["in", ["Cash", "Bank"]],
                   
                }
            };
        });

        frm.set_query("tax_account", "items", function() {
            return {
                filters: {
                    is_group     : 0,
                    company      : frm.doc.company,
                    account_type : "Tax",
                  
                }
            };
        });

    }
});

frappe.ui.form.on('Expense Entry Item', {

    supplier_name: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.supplier_name) {
            frappe.model.set_value(cdt, cdn, "tax_account", "");
            frappe.model.set_value(cdt, cdn, "vat_percentage", 0);
            return;
        }

        frappe.db.get_value("Supplier", row.supplier_name, "tax_id")
            .then(function(r) {
                if (r && r.message && r.message.tax_id) {
                    frappe.model.set_value(cdt, cdn, "tax_account", "VAT 5% - AS");
                } else {
                    frappe.model.set_value(cdt, cdn, "tax_account", "");
                    frappe.model.set_value(cdt, cdn, "vat_percentage", 0);
                }
            })
            .catch(function(error) {
                console.error("Error fetching supplier tax_id:", error);
                frappe.model.set_value(cdt, cdn, "tax_account", "");
            });
    },

    tax_account: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.tax_account) {
            frappe.db.get_value("Account", row.tax_account, "tax_rate")
                .then(function(r) {
                    if (r && r.message && r.message.tax_rate) {
                        frappe.model.set_value(cdt, cdn, "vat_percentage", flt(r.message.tax_rate));
                    } else {
                        frappe.model.set_value(cdt, cdn, "vat_percentage", 0);
                    }
                })
                .catch(function(error) {
                    console.error("Error fetching tax_rate:", error);
                    frappe.model.set_value(cdt, cdn, "vat_percentage", 0);
                });
        } else {
            frappe.model.set_value(cdt, cdn, "vat_percentage", 0);
        }
    },

    account: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
    },

    party: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (row.party_type && row.party) {
            frappe.db.get_value(row.party_type, row.party, "tax_id")
                .then(function(r) {
                    if (r && r.message && r.message.tax_id) {
                        frappe.model.set_value(cdt, cdn, "trn", r.message.tax_id);
                    } else {
                        frappe.model.set_value(cdt, cdn, "trn", "");
                    }
                })
                .catch(function(error) {
                    console.error("Error fetching tax_id:", error);
                    frappe.model.set_value(cdt, cdn, "trn", "");
                });
        } else {
            frappe.model.set_value(cdt, cdn, "trn", "");
        }
    },

    party_type: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.party_type) {
            frappe.model.set_value(cdt, cdn, "party", "");
            frappe.model.set_value(cdt, cdn, "trn", "");
        } else if (row.party) {
            frappe.db.get_value(row.party_type, row.party, "tax_id")
                .then(function(r) {
                    if (r && r.message && r.message.tax_id) {
                        frappe.model.set_value(cdt, cdn, "trn", r.message.tax_id);
                    } else {
                        frappe.model.set_value(cdt, cdn, "trn", "");
                    }
                })
                .catch(function(error) {
                    console.error("Error fetching tax_id:", error);
                    frappe.model.set_value(cdt, cdn, "trn", "");
                });
        }
    },

    amount: function(frm, cdt, cdn) {
        calculate_row_total(frm, cdt, cdn);
    },

    vat_percentage: function(frm, cdt, cdn) {
        calculate_row_total(frm, cdt, cdn);
    },

    items_remove: function(frm) {
        calculate_totals(frm);
    }
});

function calculate_row_total(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    if (row.amount && row.vat_percentage) {
        row.vat_amount   = flt(row.amount * row.vat_percentage / 100);
        row.total_amount = flt(row.amount) + flt(row.vat_amount);
    } else {
        row.vat_amount   = 0;
        row.total_amount = flt(row.amount);
    }

    frm.refresh_field('items');
    calculate_totals(frm);
}

function calculate_totals(frm) {
    let total_amount = 0;
    let total_vat    = 0;

    frm.doc.items.forEach(function(item) {
        total_amount += flt(item.amount);
        total_vat    += flt(item.vat_amount);
    });

    frm.set_value('total_amount', total_amount);
    frm.set_value('total_vat', total_vat);
    frm.set_value('grand_total', total_amount + total_vat);
}
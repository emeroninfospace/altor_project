// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

frappe.ui.form.on('Bill of Quantity', {
    refresh(frm) {
        if (frm.doc.workflow_state === "Pending" || frm.doc.workflow_state === "Approved") {
            quotaion_button(frm);
        }
    }
});

function quotaion_button(frm) {
    frm.add_custom_button(__('Quotation'), () => {
        frappe.call({
            method: 'altor_project.altor_project.doctype.bill_of_quantity.bill_of_quantity.make_quotation',
            args: {
                source_name: frm.doc.name,
                project: frm.doc.project_name
            },
            callback: function(r) {
                if (r.message) {
                    frappe.model.sync(r.message);
                    frappe.set_route('Form', r.message.doctype, r.message.name);
                }
            }
        });
    }, __('Create'));
    
}

frappe.ui.form.on('Bill of Quantity Item', {
    table_kfog_remove(frm) {
        calculate_boq_totals(frm);
        calculate_template_totals(frm);
    },
    qty(frm, cdt, cdn) {
        calculate_amount_boq(frm, cdt, cdn);
        calculate_boq_totals(frm);
        calculate_template_totals(frm);  
    },
    rate(frm, cdt, cdn) {
        calculate_amount_boq(frm, cdt, cdn);
        calculate_boq_totals(frm);
        calculate_template_totals(frm);   
    },
     item_code(frm, cdt, cdn) {
    let row = locals[cdt][cdn];

    if (row.item_code) {
        frappe.db.get_value("Item", row.item_code, ["description", "stock_uom"])
            .then(r => {
                if (r.message) {
                    let desc = r.message.description || "";  // ✅ fixed typo + null safety
                    let clean_desc = desc.replace(/<[^>]*>/g, "");

                    frappe.model.set_value(cdt, cdn, "description", clean_desc);
                    frappe.model.set_value(cdt, cdn, "uom", r.message.stock_uom);
                }
            });
    }
}


});


function calculate_amount(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    row.amount = (row.qty || 0) * (row.rate || 0);
    frm.refresh_field('table_kfog');
}
function calculate_amount_boq(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    row.amount = (row.qty || 0) * (row.rate || 0);
    frm.refresh_field('table_kfog');
}



function calculate_boq_totals(frm) {
    let total_quantity = 0;
    let total_amount = 0;

    (frm.doc.table_kfog || []).forEach(row => {
        total_quantity += row.qty || 0;
        total_amount += row.amount || 0;
    });

    frm.set_value('total_quantity_boq', total_quantity);
    frm.set_value('total_amount_boq', total_amount);

}

frappe.ui.form.on("BOQ Template Child", {
    boq_template(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.boq_template) return;
        load_boq_template_items(frm, row.boq_template);
    },

    before_boq_template_remove(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.boq_template) {
            remove_boq_template_items(frm, row.boq_template);
        }
    },

    total_amount(frm, cdt, cdn) {
        calculate_template_grand_total(frm);
    }
});

function load_boq_template_items(frm, boq_template) {
    frappe.call({
        method: "altor_project.altor_project.doctype.bill_of_quantity.bill_of_quantity.get_items",
        args: {
            item_group: boq_template
        },
        callback(r) {
            if (!r.message) return;

            (r.message || []).forEach(row => {
                let clean_description = $("<div>").html(row.description).text();
                let item = frm.add_child("table_kfog");
                item.item_code = row.item_code;
                item.boq_template_id = boq_template; 
                item.description = clean_description;
                item.uom = row.uom;
            });

            frm.refresh_field("table_kfog");
            calculate_template_totals(frm);
            calculate_boq_totals(frm)
        }
    });
}


function remove_boq_template_items(frm, boq_template) {
    frm.doc.table_kfog = (frm.doc.table_kfog || []).filter(
        d => d.boq_template_id !== boq_template
    );

    frm.refresh_field("table_kfog");
    calculate_template_totals(frm);
    calculate_boq_totals(frm)
}
function calculate_template_totals(frm) {
    let totals = {};

    (frm.doc.table_kfog || []).forEach(row => {
        if (!row.boq_template_id) return;

        if (!totals[row.boq_template_id]) {
            totals[row.boq_template_id] = { budget: 0 };
        }

        totals[row.boq_template_id].budget += flt(row.amount);
    });

    (frm.doc.boq_template || []).forEach(row => {
        let computed = totals[row.boq_template]?.budget || 0;
        if (computed > 0) {
            row.total_amount = computed;
        }
    });

    frm.refresh_field("boq_template");
    calculate_template_grand_total(frm);
}

function calculate_template_grand_total(frm) {
    let grand_total = 0;
    (frm.doc.boq_template || []).forEach(row => {
        grand_total += flt(row.total_amount);
    });
    frm.set_value('total_amount', grand_total);  
}
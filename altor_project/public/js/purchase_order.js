// Copyright (c) 2026, Emeron Infospace and contributors
// For license information, please see license.txt

// Each PO Type has its own print format; the print view opens with the one that matches the order.
const ALTOR_PO_FORMATS = {
    "General Purchase": "Altor Purchase Order",
    "Asset Purchase": "Altor Asset Purchase Order",
    "Cross Hire": "Altor Cross Hire Purchase Order",
};

frappe.ui.form.on("Purchase Order", {
    refresh: altor_po_print_format,
    custom_po_type: altor_po_print_format,
});

function altor_po_print_format(frm) {
    const format = ALTOR_PO_FORMATS[frm.doc.custom_po_type || "General Purchase"];
    if (format) frm.meta.default_print_format = format;
}

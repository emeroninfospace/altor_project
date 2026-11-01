import frappe


def get_property_setters():
    return [
        get_options_property_setter(
            "Quotation",
            "naming_series",
            ["QTN-.YYYY.-","SAL-QTN-.YYYY.-"],
        ),
        get_options_property_setter(
            "Sales Invoice",
            "naming_series",
            ["Altor-SI-.YYYY.-","Altor-RET-.YYYY.-","ACC-SINV-.YYYY.-","ACC-SINV-RET-.YYYY.-"],
        ),
        get_options_property_setter(
            "Purchase Invoice",
            "naming_series",
            ["Altor-PI-.YYYY.-","Altor-PI-RET-.YYYY.-","ACC-PINV-.YYYY.-","ACC-PINV-RET-.YYYY.-"],
        ),
        get_options_property_setter(
            "Purchase Order",
            "naming_series",
            ["Altor-PO-.YYYY.-"],
        ),
        get_options_property_setter(
            "Project",
            "naming_series",
            ["Altor-PR-.YYYY.-"],
        ),
        {
         "doctype": "Quotation",
         "fieldname":"ignore_pricing_rule",
         "is_system_generated": 0,
         "property": "hidden",
         "value": "1"
         },
         {
         "doctype": "Quotation",
         "fieldname":"scan_barcode",
         "is_system_generated": 0,
         "property": "hidden",
         "value": "1"
         },
         {
         "doctype": "Quotation",
         "fieldname":"last_scanned_warehouse",
         "is_system_generated": 0,
         "property": "hidden",
         "value": "1"
         },
         {
         "doctype": "Quotation",
         "fieldname":"shipping_rule",
         "is_system_generated": 0,
         "property": "hidden",
         "value": "1"
         },
         {
         "doctype": "Quotation",
         "fieldname":"incoterm",
         "is_system_generated": 0,
         "property": "hidden",
         "value": "1"
         },
         {
         "doctype": "Quotation",
         "fieldname":"named_place",
         "is_system_generated": 0,
         "property": "hidden",
         "value": "1"
         },
         {
         "doctype": "Quotation",
         "fieldname":"auto_repeat",
         "is_system_generated": 0,
         "property": "hidden",
         "value": "1"
         },
         {
         "doctype": "Quotation",
         "fieldname":"update_auto_repeat_reference",
         "is_system_generated": 0,
         "property": "hidden",
         "value": "1"
         },
         {
         "doctype": "Quotation",
         "fieldname":"subscription_section",
         "is_system_generated": 0,
         "property": "hidden",
         "value": "1"
         },
         {
            "doctype": "Quotation",
            "fieldname":"order_type",
            "is_system_generated": 0,
            "property": "hidden",
            "value": "1"
         }
    ]
def get_options_property_setter(doctype, fieldname, new_options, prepend=True):
    existing_options = frappe.get_meta(doctype).get_options(fieldname).split("\n")
    if prepend:
        options = new_options + existing_options
    else:
        options = existing_options + new_options

    # using dict.fromkeys to get unique ordered options
    # https://stackoverflow.com/a/53657523/4767738
    options = "\n".join(dict.fromkeys(options))

    return {
        "doctype": doctype,
        "fieldname": fieldname,
        "property": "options",
        "is_system_generated": 0,  
        "value": options,
    }
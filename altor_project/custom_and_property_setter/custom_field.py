CREATE_FIELDS={
        "Quotation": [
            {
                "fieldname": "custom_bill_of_quantity",
                "label": "Bill of Quantity",
                "fieldtype": "Link",
                "options": "Bill of Quantity",
                "insert_after": "valid_till"
            },
            {
                "fieldname": "custom_project",
                "label": "Project",
                "fieldtype": "Data",
                "insert_after": "order_type"
            },
            {
                "fieldname": "custom_location",
                "label": "Location",
                "fieldtype": "Data",
                "insert_after": "custom_project"
            },
            {
                "fieldname": "custom_scope_of_work",
                "label": "Scope of Work",
                "fieldtype": "Small Text",
                "insert_after": "custom_location"
            },
            {
                "fieldname": "lpo_ref",
                "label": "LPO Ref",
                "fieldtype": "Data",
                "insert_after": "custom_scope_of_work"
            },
            {
                "fieldname": "lpo_date",
                "label": "LPO Date",
                "fieldtype": "Date",
                "insert_after": "lpo_ref"
            }
           

        ],
        "Project": [
           
           
            {
                "fieldname": "quotation",
                "label": "Quotation",
                "fieldtype": "Link",
                "options": "Quotation",
                "read_only":1,
                "insert_after": "custom_bill_of_quantity"
            },
            {
                "fieldname": "location",
                "label": "Location",
                "fieldtype": "Data",
                "insert_after": "quotation"
            },
            {
                "fieldname": "scope_of_work",
                "label": "Scope of Work",
                "fieldtype": "Small Text",
                "insert_after": "location"
            },
            {
                "fieldname": "custom_connections",
                "label": "Connections",
                "fieldtype": "Tab Break",
                "insert_after": "message",
                "show_dashboard": 1
            },
            
         
            {
                "fieldname": "custom_section_break003",
                "fieldtype": "Section Break",
                "insert_after": "scope_of_work",
                "label": "BOQ Items",
                "collapsible": 1
            },
            {
                "fieldname": "custom_boq_items",
                "fieldtype": "Table",
                "insert_after": "custom_section_break003",
                "label": "BOQ Items",
                "options": "BOQ Items"
            },
            {
                "fieldname": "custom_bill_of_quantity",
                "fieldtype": "Link",
                "insert_after": "department",
                "label": "Bill of Quantity",
                "options": "Bill of Quantity",
                "read_only":1
            },
            {
                "fieldname": "lpo_ref",
                "label": "LPO Ref",
                "fieldtype": "Data",
                "insert_after": "percent_complete_method"
            },
            {
                "fieldname": "lpo_date",
                "label": "LPO Date",
                "fieldtype": "Date",
                "insert_after": "lpo_ref"
            },
        ],
        "Sales Invoice": [
            {
                "fieldname": "custom_quotation",
                "label": "Quotation",
                "fieldtype": "Link",
                "options": "Quotation",
                "insert_after": "customer"
            },
        ],
         "Material Request": [
            {
                "fieldname": "custom_project",
                "label": "Project",
                "fieldtype": "Link",
                "options": "Project",
                "insert_after": "amended_from"
            },
        ],
        "Material Request Item": [
        {
            "fieldname": "custom_size",
            "label": "Size",
            "fieldtype": "Float",
            "insert_after": "qty",
            "in_list_view": 1,
            "columns": 1
        },
        {
            "fieldname": "custom_length",
            "label": "Length",
            "fieldtype": "Float",
            "insert_after": "custom_size",
            "in_list_view": 1,
            "columns": 1
        }
    ],
    "Task": [
            {
                "fieldname": "custom_bill_of_quantity",
                "label": "Bill of Quantity",
                "fieldtype": "Link",
                "options" : "Bill of Quantity",
                "read_only": 1,
                "insert_after": "parent_task"
            },
            {
                "fieldname": "custom_project_schedule",
                "label": "Project Schedule",
                "fieldtype": "Link",
                "options" : "Project Schedule",
                "read_only": 1,
                "insert_after": "custom_bill_of_quantity",
            },
        ],
    "Journal Entry": [
        {
                "fieldname": "custom_project",
                "label": "Project",
                "fieldtype": "Link",
                "options" : "Project",
                "read_only": 1,
                "insert_after": "tax_withholding_category"
        }
    ]
    ,
    # Manpower costing (own staff and outsourced manpower)
    "Employee": [
        {
            "fieldname": "custom_manpower_costing_section",
            "label": "Manpower Costing",
            "fieldtype": "Section Break",
            "collapsible": 1,
            "insert_after": "reports_to",
        },
        {
            "fieldname": "custom_is_outsourced",
            "label": "Outsourced Manpower",
            "fieldtype": "Check",
            "in_standard_filter": 1,
            "description": "Worker supplied by a manpower agency",
            "insert_after": "custom_manpower_costing_section",
        },
        {
            "fieldname": "custom_manpower_supplier",
            "label": "Manpower Supplier / Agency",
            "fieldtype": "Link",
            "options": "Supplier",
            "depends_on": "eval:doc.custom_is_outsourced",
            "mandatory_depends_on": "eval:doc.custom_is_outsourced",
            "insert_after": "custom_is_outsourced",
        },
        {
            "fieldname": "custom_manpower_column_break",
            "fieldtype": "Column Break",
            "insert_after": "custom_manpower_supplier",
        },
        {
            "fieldname": "custom_hourly_cost_rate",
            "label": "Hourly Cost Rate",
            "fieldtype": "Currency",
            "description": "Cost per hour. Leave empty to use the agency rate (outsourced) or CTC / working hours (own staff) from Altor Settings",
            "insert_after": "custom_manpower_column_break",
        },
        {
            "fieldname": "custom_ot_hourly_rate",
            "label": "OT Hourly Rate",
            "fieldtype": "Currency",
            "description": "Leave empty to use Hourly Cost Rate x OT Multiplier",
            "insert_after": "custom_hourly_cost_rate",
        },
    ],
    "Purchase Invoice": [
        {
            "fieldname": "custom_is_manpower_invoice",
            "label": "Outsourced Manpower Invoice",
            "fieldtype": "Check",
            "description": "Agency invoice for manpower already recorded in Manpower Entries. It is left out of the Project Budget so labour cost is not counted twice.",
            "insert_after": "supplier",
        },
    ],
}

# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

"""Fields printed on the ALTOR document designs (see altor_project.print_forms).

Merged into custom_field.CREATE_FIELDS. Most are plain text the buyer / dispatcher types once;
anything the system already holds (supplier, project, dates, warehouse...) is read from the
standard fields instead.
"""

GENERAL = 'eval:!doc.custom_po_type || doc.custom_po_type=="General Purchase"'
ASSET = 'eval:doc.custom_po_type=="Asset Purchase"'
HIRE = 'eval:doc.custom_po_type=="Cross Hire"'
GENERAL_OR_ASSET = 'eval:doc.custom_po_type!="Cross Hire"'
GENERAL_OR_HIRE = 'eval:doc.custom_po_type!="Asset Purchase"'

DN_TRADING = 'eval:!doc.custom_dn_type || doc.custom_dn_type=="Trading DN"'
DN_CONTRACT = 'eval:in_list(["Own Asset - Contract", "Cross Hire - Contract"], doc.custom_dn_type)'
DN_HIRE = 'eval:in_list(["Own Asset - Hire", "Cross Hire - Hire"], doc.custom_dn_type)'


def _fields(rows, first_after):
	"""[(fieldname, fieldtype, label, extra)] -> custom field dicts, each inserted after the previous."""
	out, after = [], first_after
	for fieldname, fieldtype, label, extra in rows:
		field = {"fieldname": fieldname, "fieldtype": fieldtype, "insert_after": after}
		if label:
			field["label"] = label
		field.update(extra or {})
		out.append(field)
		after = fieldname
	return out


PO_HEADER = _fields(
	[
		(
			"custom_po_type",
			"Select",
			"PO Type",
			{
				"options": "General Purchase\nAsset Purchase\nCross Hire",
				"default": "General Purchase",
				"in_standard_filter": 1,
				"description": "Chooses the printed layout and terms: general purchase, asset purchase or cross hire",
			},
		),
		("custom_revision", "Data", "Revision", {"default": "00", "length": 10}),
	],
	"schedule_date",
)

PO_INSTRUCTIONS = _fields(
	[
		("custom_order_instructions_tab", "Tab Break", "Order Instructions", None),
		("custom_order_instructions_section", "Section Break", "Printed on the Purchase Order", None),
		(
			"custom_pr_reference",
			"Data",
			"PR / Enquiry Reference",
			{"description": "Left empty: the Material Requests of the items"},
		),
		(
			"custom_supplier_quote_ref",
			"Data",
			"Supplier Quote Ref. / Date",
			{"description": "Left empty: the Supplier Quotations of the items"},
		),
		(
			"custom_delivery_location",
			"Small Text",
			"Delivery / Hire Location",
			{"description": "Left empty: the shipping address"},
		),
		("custom_site_contact", "Data", "Site Contact / Phone", None),
		(
			"custom_delivery_terms",
			"Data",
			"Delivery / Transport Terms",
			{"description": "Left empty: the Incoterm"},
		),
		(
			"custom_invoice_email",
			"Data",
			"Invoice Submission Email",
			{"options": "Email", "depends_on": GENERAL},
		),
		("custom_order_instructions_cb", "Column Break", None, None),
		("custom_delivery_schedule", "Data", "Delivery Schedule", {"depends_on": GENERAL}),
		(
			"custom_partial_delivery",
			"Select",
			"Partial Delivery Permitted?",
			{"options": "\nYes\nNo", "depends_on": GENERAL},
		),
		("custom_dn_requirements", "Data", "Delivery Note Requirements", {"depends_on": GENERAL}),
		("custom_scope_exclusions", "Small Text", "Scope / Exclusions", {"depends_on": GENERAL}),
		(
			"custom_required_documents",
			"Small Text",
			"Required Documents / Certificates",
			{"depends_on": GENERAL_OR_ASSET},
		),
		("custom_warranty_period", "Data", "Warranty Period / Start Event", {"depends_on": GENERAL_OR_ASSET}),
		(
			"custom_acceptance_criteria",
			"Small Text",
			"Acceptance Criteria / Milestones",
			{"depends_on": GENERAL_OR_ASSET},
		),
		(
			"custom_special_conditions",
			"Small Text",
			"Special Conditions / Attachment",
			{"depends_on": GENERAL_OR_HIRE},
		),
		("custom_asset_po_section", "Section Break", "Asset Purchase", {"depends_on": ASSET}),
		("custom_asset_condition", "Select", "Asset Condition", {"options": "\nNew\nUsed"}),
		("custom_testing_commissioning", "Data", "Testing / Commissioning", None),
		("custom_training_support", "Data", "Training / Spares / Support", None),
		("custom_payment_milestones", "Data", "Payment Milestones / Attachment", None),
		("custom_asset_po_cb", "Column Break", None, None),
		("custom_asset_spec_ref", "Data", "Asset Class / Specification Ref.", None),
		("custom_inspection_location", "Data", "Inspection Location", None),
		("custom_warranty_response", "Data", "Warranty Response Time", None),
		("custom_cross_hire_section", "Section Break", "Cross Hire", {"depends_on": HIRE}),
		("custom_hire_from", "Date", "Est. Hire From", None),
		("custom_hire_to", "Date", "Est. Hire To", None),
		("custom_min_hire", "Data", "Minimum Hire / Off-hire Notice", None),
		("custom_collection_party", "Data", "Collection / Return Party", None),
		("custom_billing_cycle", "Data", "Proration / Billing Cycle", None),
		("custom_mobilization", "Data", "Mobilization / Demobilization", None),
		("custom_cross_hire_cb", "Column Break", None, None),
		("custom_breakdown_time", "Data", "Breakdown Replacement Time", None),
		("custom_operator_fuel", "Data", "Operator / Fuel / Maintenance", None),
		("custom_loading", "Data", "Loading / Unloading / Installation", None),
		("custom_loss_damage_rates", "Data", "Loss / Damage Rate Schedule", None),
		("custom_permitted_sites", "Data", "Permitted Sites / Insurance Scope", None),
		("custom_hire_type", "Data", "Hire Type / Restrictions", None),
	],
	"terms",
)

PO_ITEM = _fields(
	[
		("custom_make_reference", "Data", "Reference / Make", None),
		(
			"custom_hire_basis",
			"Select",
			"Hire Basis",
			{
				"options": "\nHour\nDay\nWeek\nMonth\nOne-off",
				"depends_on": 'eval:parent.custom_po_type=="Cross Hire"',
			},
		),
		(
			"custom_hire_periods",
			"Float",
			"Est. Periods",
			{
				"depends_on": 'eval:parent.custom_po_type=="Cross Hire" && doc.custom_hire_basis!="One-off"',
				"description": "Quantity = units x periods (100 Nos for 4 weeks = 400) and Rate = rate per period. "
				"The PO prints 100 units, Week, 4 periods.",
			},
		),
	],
	"item_name",
)

DN_FIELDS = _fields(
	[
		(
			"custom_dn_type",
			"Select",
			"Delivery Note Type",
			{
				"options": "Trading DN\nOwn Asset - Contract\nOwn Asset - Hire\nCross Hire - Contract\nCross Hire - Hire",
				"default": "Trading DN",
				"in_standard_filter": 1,
				"description": "Chooses the printed layout and delivery conditions",
			},
		),
	],
	"set_posting_time",
) + _fields(
	[
		("custom_dn_print_section", "Section Break", "Delivery Note Details", {"collapsible": 1}),
		("custom_site_contact", "Data", "Site Contact / Phone", None),
		("custom_issue_reference", "Data", "Issue Reference", None),
		("custom_delivery_status", "Select", "Delivery Status", {"options": "\nComplete\nPartial\nFinal"}),
		(
			"custom_related_dn",
			"Link",
			"Related Previous DN",
			{"options": "Delivery Note", "depends_on": DN_TRADING},
		),
		("custom_delivery_schedule", "Data", "Customer Delivery Schedule", {"depends_on": DN_TRADING}),
		("custom_packing_ref", "Data", "Packing / Shipment Ref.", {"depends_on": DN_TRADING}),
		("custom_dn_print_cb", "Column Break", None, None),
		("custom_work_package", "Data", "Work Package / Area", {"depends_on": DN_CONTRACT}),
		("custom_expected_return_date", "Date", "Expected Return / Review Date", {"depends_on": DN_CONTRACT}),
		("custom_mobilisation_ref", "Data", "Mobilisation Reference", {"depends_on": DN_CONTRACT}),
		("custom_on_hire_date", "Date", "Agreed On-hire Date", {"depends_on": DN_HIRE}),
		("custom_hire_agreement", "Data", "Hire Agreement / Schedule", {"depends_on": DN_HIRE}),
		("custom_hire_start_basis", "Data", "Hire Start Basis", {"depends_on": DN_HIRE}),
	],
	"lr_date",
)

SI_FIELDS = _fields(
	[
		(
			"custom_date_of_supply",
			"Date",
			"Date of Supply",
			{"description": "Left empty: the date of the linked Delivery Notes, else the invoice date"},
		),
		("custom_billing_period", "Data", "Billing Period", {"description": "e.g. 01-11-2026 to 30-11-2026"}),
		("custom_certificate_reference", "Data", "Payment Certificate / IPC Ref.", None),
	],
	"due_date",
) + _fields(
	[
		(
			"custom_tax_note",
			"Small Text",
			"Notes / Tax Treatment",
			{"description": "Printed under the totals (e.g. zero-rated or reverse-charge statement)"},
		)
	],
	"terms",
)

PRINT_FIELDS = {
	"Purchase Order": PO_HEADER + PO_INSTRUCTIONS,
	"Purchase Order Item": PO_ITEM,
	"Delivery Note": DN_FIELDS,
	"Sales Invoice": SI_FIELDS,
}

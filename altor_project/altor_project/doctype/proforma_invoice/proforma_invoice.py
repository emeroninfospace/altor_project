# Copyright (c) 2026, Emeron Infospace and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import flt, getdate, nowdate
from collections import defaultdict

from erpnext.controllers.selling_controller import SellingController

form_grid_templates = {"items": "templates/form_grid/item_grid.html"}


class ProformaInvoice(SellingController):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from erpnext.accounts.doctype.payment_schedule.payment_schedule import PaymentSchedule
		from erpnext.accounts.doctype.pricing_rule_detail.pricing_rule_detail import PricingRuleDetail
		from erpnext.accounts.doctype.sales_taxes_and_charges.sales_taxes_and_charges import (
			SalesTaxesandCharges,
		)
		from erpnext.crm.doctype.competitor_detail.competitor_detail import CompetitorDetail
		from altor_project.altor_project.doctype.proforma_invoice_item.proforma_invoice_item import (
			ProformaInvoiceItem,
		)
		from erpnext.setup.doctype.quotation_lost_reason_detail.quotation_lost_reason_detail import (
			QuotationLostReasonDetail,
		)
		from erpnext.stock.doctype.packed_item.packed_item import PackedItem

		additional_discount_percentage: DF.Float
		address_display: DF.SmallText | None
		amended_from: DF.Link | None
		apply_discount_on: DF.Literal["", "Grand Total", "Net Total"]
		auto_repeat: DF.Link | None
		base_discount_amount: DF.Currency
		base_grand_total: DF.Currency
		base_in_words: DF.Data | None
		base_net_total: DF.Currency
		base_rounded_total: DF.Currency
		base_rounding_adjustment: DF.Currency
		base_total: DF.Currency
		base_total_taxes_and_charges: DF.Currency
		campaign: DF.Link | None
		company: DF.Link
		company_address: DF.Link | None
		company_address_display: DF.SmallText | None
		company_contact_person: DF.Link | None
		competitors: DF.TableMultiSelect[CompetitorDetail]
		contact_display: DF.SmallText | None
		contact_email: DF.Data | None
		contact_mobile: DF.SmallText | None
		contact_person: DF.Link | None
		conversion_rate: DF.Float
		coupon_code: DF.Link | None
		currency: DF.Link
		customer_address: DF.Link | None
		customer_group: DF.Link | None
		customer_name: DF.Data | None
		disable_rounded_total: DF.Check
		discount_amount: DF.Currency
		enq_det: DF.Text | None
		grand_total: DF.Currency
		group_same_items: DF.Check
		has_unit_price_items: DF.Check
		ignore_pricing_rule: DF.Check
		in_words: DF.Data | None
		incoterm: DF.Link | None
		items: DF.Table[ProformaInvoiceItem]
		language: DF.Data | None
		letter_head: DF.Link | None
		lost_reasons: DF.TableMultiSelect[QuotationLostReasonDetail]
		named_place: DF.Data | None
		naming_series: DF.Literal["PROF-INV-.YYYY.-"]
		net_total: DF.Currency
		opportunity: DF.Link | None
		order_lost_reason: DF.SmallText | None
		order_type: DF.Literal["", "Sales", "Maintenance", "Shopping Cart"]
		other_charges_calculation: DF.TextEditor | None
		packed_items: DF.Table[PackedItem]
		party_name: DF.DynamicLink | None
		payment_schedule: DF.Table[PaymentSchedule]
		payment_terms_template: DF.Link | None
		plc_conversion_rate: DF.Float
		price_list_currency: DF.Link
		pricing_rules: DF.Table[PricingRuleDetail]
		proforma_invoice_to: DF.Link
		referral_sales_partner: DF.Link | None
		rounded_total: DF.Currency
		rounding_adjustment: DF.Currency
		scan_barcode: DF.Data | None
		select_print_heading: DF.Link | None
		selling_price_list: DF.Link
		shipping_address: DF.SmallText | None
		shipping_address_name: DF.Link | None
		shipping_rule: DF.Link | None
		source: DF.Link | None
		status: DF.Literal[
			"Draft", "Open", "Replied", "Partially Ordered", "Ordered", "Lost", "Cancelled", "Expired"
		]
		supplier_quotation: DF.Link | None
		tax_category: DF.Link | None
		taxes: DF.Table[SalesTaxesandCharges]
		taxes_and_charges: DF.Link | None
		tc_name: DF.Link | None
		terms: DF.TextEditor | None
		territory: DF.Link | None
		title: DF.Data | None
		total: DF.Currency
		total_net_weight: DF.Float
		total_qty: DF.Float
		total_taxes_and_charges: DF.Currency
		transaction_date: DF.Date
		valid_till: DF.Date | None
	# end: auto-generated types

	def set_indicator(self):
		if self.docstatus == 1:
			self.indicator_color = "blue"
			self.indicator_title = "Submitted"
		if self.valid_till and getdate(self.valid_till) < getdate(nowdate()):
			self.indicator_color = "gray"
			self.indicator_title = "Expired"

	def before_validate(self):
		self.set_has_unit_price_items()
		self.flags.allow_zero_qty = self.has_unit_price_items

	def validate(self):
		super().validate()
		self.set_status()
		self.validate_uom_is_integer("stock_uom", "stock_qty")
		self.validate_uom_is_integer("uom", "qty")
		self.validate_valid_till()
		self.set_customer_name()
		self.over_billing()
		if self.items:
			self.with_items = 1

		from erpnext.stock.doctype.packed_item.packed_item import make_packing_list

		make_packing_list(self)

	def calculate_taxes_and_totals(self):
		"""
		Override to ensure Proforma Invoice is treated like Quotation for tax calculations.
		This prevents the AttributeError when tax.category doesn't exist.
		"""
		from erpnext.controllers.taxes_and_totals import calculate_taxes_and_totals as calc_taxes
		from erpnext.controllers import taxes_and_totals
		
		# Store original calculate_totals if not already patched
		if not hasattr(taxes_and_totals.calculate_taxes_and_totals, '_proforma_patched'):
			original_calculate_totals = taxes_and_totals.calculate_taxes_and_totals.calculate_totals
			
			def patched_calculate_totals(self):
				"""Patched version that includes Proforma Invoice in selling doctypes"""
				from frappe.utils import flt
				
				grand_total_diff = getattr(self, "grand_total_diff", 0)

				if self.doc.get("taxes"):
					self.doc.grand_total = flt(self.doc.get("taxes")[-1].total) + grand_total_diff
				else:
					self.doc.grand_total = flt(self.doc.net_total)

				if self.doc.get("taxes"):
					self.doc.total_taxes_and_charges = flt(
						self.doc.grand_total - self.doc.net_total - grand_total_diff,
						self.doc.precision("total_taxes_and_charges"),
					)
				else:
					self.doc.total_taxes_and_charges = 0.0

				self._set_in_company_currency(self.doc, ["total_taxes_and_charges"])

				# Add Proforma Invoice to the list of selling doctypes
				if self.doc.doctype in [
					"Quotation",
					"Sales Order",
					"Delivery Note",
					"Sales Invoice",
					"POS Invoice",
					"Proforma Invoice",  # Added here
				]:
					self.doc.base_grand_total = (
						flt(self.doc.grand_total * self.doc.conversion_rate, self.doc.precision("base_grand_total"))
						if self.doc.total_taxes_and_charges
						else self.doc.base_net_total
					)
				else:
					self.doc.taxes_and_charges_added = self.doc.taxes_and_charges_deducted = 0.0
					for tax in self.doc.get("taxes"):
						# Safely check for category attribute
						tax_category = getattr(tax, "category", None)
						if tax_category and tax_category in ["Valuation and Total", "Total"]:
							if tax.add_deduct_tax == "Add":
								self.doc.taxes_and_charges_added += flt(tax.tax_amount_after_discount_amount)
							else:
								self.doc.taxes_and_charges_deducted += flt(tax.tax_amount_after_discount_amount)

					self.doc.round_floats_in(self.doc, ["taxes_and_charges_added", "taxes_and_charges_deducted"])

					self.doc.base_grand_total = (
						flt(self.doc.grand_total * self.doc.conversion_rate)
						if (self.doc.taxes_and_charges_added or self.doc.taxes_and_charges_deducted)
						else self.doc.base_net_total
					)

					self._set_in_company_currency(self.doc, ["taxes_and_charges_added", "taxes_and_charges_deducted"])

				self.doc.round_floats_in(self.doc, ["grand_total", "base_grand_total"])

				self.set_rounded_total()
			
			# Apply the patch
			taxes_and_totals.calculate_taxes_and_totals.calculate_totals = patched_calculate_totals
			taxes_and_totals.calculate_taxes_and_totals._proforma_patched = True
		
		# Now call the standard calculation
		calc_taxes(self)

	def before_submit(self):
		self.set_has_alternative_item()

	def validate_valid_till(self):
		if self.valid_till and getdate(self.valid_till) < getdate(self.transaction_date):
			frappe.throw(_("Valid till date cannot be before transaction date"))

	def set_has_alternative_item(self):
		"""Mark 'Has Alternative Item' for rows."""
		if not any(row.is_alternative for row in self.get("items")):
			return

		items_with_alternatives = self.get_rows_with_alternatives()
		for row in self.get("items"):
			if not row.is_alternative and row.name in items_with_alternatives:
				row.has_alternative_item = 1

	def set_has_unit_price_items(self):
		"""
		If permitted in settings and any item has 0 qty, the Proforma Invoice has unit price items.
		"""
		if not frappe.db.get_single_value("Selling Settings", "allow_zero_qty_in_quotation"):
			return

		self.has_unit_price_items = any(
			not row.qty for row in self.get("items") if (row.item_code and not row.qty)
		)

	def set_customer_name(self):
		if self.party_name and self.proforma_invoice_to == "Customer":
			self.customer_name = frappe.db.get_value("Customer", self.party_name, "customer_name")
		elif self.party_name and self.proforma_invoice_to == "Lead":
			lead_name, company_name = frappe.db.get_value(
				"Lead", self.party_name, ["lead_name", "company_name"]
			)
			self.customer_name = company_name or lead_name
		elif self.party_name and self.proforma_invoice_to == "Prospect":
			self.customer_name = self.party_name
		elif self.party_name and self.proforma_invoice_to == "CRM Deal":
			self.customer_name = frappe.db.get_value("CRM Deal", self.party_name, "organization")

	def update_lead(self):
		if self.proforma_invoice_to == "Lead" and self.party_name:
			frappe.get_doc("Lead", self.party_name).set_status(update=True)

	def update_opportunity(self, status):
		for opportunity in set(d.prevdoc_docname for d in self.get("items")):
			if opportunity:
				self.update_opportunity_status(status, opportunity)

		if self.opportunity:
			self.update_opportunity_status(status)

	def update_opportunity_status(self, status, opportunity=None):
		if not opportunity:
			opportunity = self.opportunity

		opp = frappe.get_doc("Opportunity", opportunity)
		opp.set_status(status=status, update=True)

	@frappe.whitelist()
	def declare_enquiry_lost(self, lost_reasons_list, competitors, detailed_reason=None):
		if not (self.is_fully_ordered() or self.is_partially_ordered()):
			get_lost_reasons = frappe.get_list("Quotation Lost Reason", fields=["name"])
			lost_reasons_lst = [reason.get("name") for reason in get_lost_reasons]
			self.db_set("status", "Lost")

			if detailed_reason:
				self.db_set("order_lost_reason", detailed_reason)

			for reason in lost_reasons_list:
				if reason.get("lost_reason") in lost_reasons_lst:
					self.append("lost_reasons", reason)
				else:
					frappe.throw(
						_("Invalid lost reason {0}, please create a new lost reason").format(
							frappe.bold(reason.get("lost_reason"))
						)
					)

			for competitor in competitors:
				self.append("competitors", competitor)

			self.update_opportunity("Lost")
			self.update_lead()
			self.save()

		else:
			frappe.throw(_("Cannot set as Lost as Sales Order is made."))

	def on_submit(self):
		# Check for Approving Authority
		frappe.get_doc("Authorization Control").validate_approving_authority(
			self.doctype, self.company, self.base_grand_total, self
		)

		# update enquiry status
		self.update_opportunity("Quotation")
		self.update_lead()

	def on_cancel(self):
		if self.lost_reasons:
			self.lost_reasons = []
		super().on_cancel()

		# update enquiry status
		self.set_status(update=True)
		self.update_opportunity("Open")
		self.update_lead()

	def on_recurring(self, reference_doc, auto_repeat_doc):
		self.valid_till = None

	def get_rows_with_alternatives(self):
		rows_with_alternatives = []
		table_length = len(self.get("items"))

		for idx, row in enumerate(self.get("items")):
			if row.is_alternative:
				continue

			if idx == (table_length - 1):
				break

			if self.get("items")[idx + 1].is_alternative:
				rows_with_alternatives.append(row.name)

		return rows_with_alternatives

	def is_fully_ordered(self):
		ordered_items = self.get_ordered_items(self.name)
		if not ordered_items:
			return False
		
		self._items = (
			self.get_valid_items()
			if any(row.is_alternative for row in self.get("items"))
			else self.get("items")
		)

		for row in self._items:
			if row.name not in ordered_items or row.qty > ordered_items[row.name]:
				return False

		return True

	def is_partially_ordered(self):
		ordered_items = self.get_ordered_items(self.name)
		if not ordered_items:
			return False
		
		self._items = (
			self.get_valid_items()
			if any(row.is_alternative for row in self.get("items"))
			else self.get("items")
		)

		for row in self._items:
			if row.name not in ordered_items or row.qty > ordered_items[row.name]:
				return True

		return False

	def get_ordered_items(self, proforma_invoice_name):
		"""Returns a dict of ordered items with their total qty based on proforma invoice row name."""
		# Note: This will work if Sales Order Item has a field linking to Proforma Invoice Item
		# You may need to add a custom field or adjust this based on your requirements
		ordered_data = frappe.get_all(
			"Sales Order Item",
			filters={"prevdoc_docname": proforma_invoice_name, "docstatus": 1},
			fields=["name", "sum(qty) as qty"],
			group_by="name",
			as_list=1,
		)
		return frappe._dict(ordered_data) if ordered_data else frappe._dict()

	def get_valid_items(self):
		"""Filters out items in an alternatives set that were not ordered."""

		def is_in_sales_order(row):
			in_sales_order = bool(
				frappe.db.exists(
					"Sales Order Item",
					{"prevdoc_docname": self.name, "item_code": row.item_code, "docstatus": 1},
				)
			)
			return in_sales_order

		def can_map(row) -> bool:
			if row.is_alternative or row.has_alternative_item:
				return is_in_sales_order(row)

			return True

		return list(filter(can_map, self.get("items")))

	def over_billing(self):
		if not self.quotation:
			return

		quotation_total = frappe.db.get_value(
			"Quotation", self.quotation, "grand_total"
		) or 0

		billed = frappe.db.sql("""
			SELECT SUM(grand_total)
			FROM `tabProforma Invoice`
			WHERE quotation = %s
			AND docstatus = 1
			AND name != %s
		""", (self.quotation, self.name))[0][0] or 0

		if billed + self.grand_total > quotation_total:
			frappe.throw(
				"Proforma Invoice amount exceeds remaining Quotation balance."
			)
		
		



@frappe.whitelist()
def load_target_items(docname):
    """
    Load checked target items from items table to custom_service_item table
    """
    doc = frappe.get_doc('Proforma Invoice', docname)
    
    # Get checked items
    checked_items = [item for item in doc.items if item.custom_target_items == 1]
    
    if not checked_items:
        frappe.msgprint(_('No items are marked as target items'))
        return
    
    # Get existing item codes in custom_service_item to avoid duplicates
    existing_item_codes = [row.item_code for row in doc.custom_service_item if row.item_code]
    
    # Add to service items table (append to existing items)
    added_count = 0
    for item in checked_items:
        # Skip if item already exists in custom_service_item table
        if item.item_code in existing_item_codes:
            continue
            
        service_item = doc.append('custom_service_item', {})
        service_item.item_code = item.item_code
        service_item.item_name = item.item_name
        service_item.description = item.description
        service_item.qty = item.qty
        service_item.warehouse = item.warehouse
        service_item.uom = item.uom
        service_item.rate = item.rate
        service_item.amount = item.amount
        
        # Required fields for custom_service_item
        # UOM Conversion Factor
        service_item.conversion_factor = getattr(item, 'conversion_factor', None) or 1.0
        
        # Rate (Company Currency) - use base_rate if available, otherwise use rate
        service_item.base_rate = getattr(item, 'base_rate', None) or item.rate
        
        # Amount (Company Currency) - use base_amount if available, otherwise use amount
        service_item.base_amount = getattr(item, 'base_amount', None) or item.amount
        
        # Income Account - try to get from item, or fetch from item defaults
        income_account = getattr(item, 'income_account', None)
        if not income_account and item.item_code:
            # Try to get income account from item defaults for the company
            try:
                income_account = frappe.get_value(
                    'Item Default',
                    {'parent': item.item_code, 'company': doc.company},
                    'income_account'
                )
                # If not found in item defaults, try to get from item group or brand
                if not income_account:
                    item_doc = frappe.get_doc('Item', item.item_code)
                    if hasattr(item_doc, 'item_group') and item_doc.item_group:
                        income_account = frappe.get_value('Item Group', item_doc.item_group, 'income_account')
            except:
                pass
        
        service_item.income_account = income_account
        added_count += 1
    
    # Calculate totals from custom_service_item table
    total_qty = sum(flt(item.qty) or 0 for item in doc.custom_service_item)
    total_amount = sum(flt(item.amount) or 0 for item in doc.custom_service_item)
    
    doc.consumable_total_quantity = total_qty
    doc.consumable_total = total_amount
    
    if added_count == 0:
        frappe.msgprint(_('No new items to add. All selected items already exist in service items table.'))
    else:
        doc.save()
        frappe.msgprint(_(f'{added_count} item(s) added successfully'))
    
    return doc.as_dict()




@frappe.whitelist()
def make_proforma_invoice(quotation):

    quotation_doc = frappe.get_doc("Quotation", quotation)

    billed_qty_map = defaultdict(float)

    billed_items = frappe.db.sql("""
    SELECT
        pii.item_code,
        SUM(pii.qty) AS billed_qty
    FROM `tabProforma Invoice Item` pii
    INNER JOIN `tabProforma Invoice` pi
        ON pi.name = pii.parent
    WHERE pi.quotation = %s
    AND pi.docstatus = 1
    GROUP BY pii.item_code
""", quotation, as_dict=True)


    for row in billed_items:
        billed_qty_map[row.item_code] = row.billed_qty or 0


    pi = get_mapped_doc(
        "Quotation",
        quotation,
        {
            "Quotation": {
                "doctype": "Proforma Invoice",
                "field_map": {
                    "name": "quotation"
                }
            },
            "Quotation Item": {
                "doctype": "Proforma Invoice Item",
                "field_map": {
                    "name": "quotation_item"
                }
            }
        }
    )


    remaining_items = []

    for item in pi.items:
        quotation_item_qty = frappe.db.get_value(
			"Quotation Item",
			{
				"parent": quotation,
				"item_code": item.item_code
			},
			"qty"
		) or 0

        billed_qty = billed_qty_map.get(item.item_code, 0)
        remaining_qty = quotation_item_qty - billed_qty


        if remaining_qty > 0:
            item.qty = remaining_qty
            item.amount = remaining_qty * item.rate
            remaining_items.append(item)

    pi.set("items", remaining_items)

    if not pi.items:
        frappe.throw(
            "All items in this Quotation are already fully billed."
        )


    pi.run_method("calculate_taxes_and_totals")

    return pi


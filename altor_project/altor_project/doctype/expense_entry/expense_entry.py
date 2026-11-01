# Copyright (c) 2026, emeron and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class ExpenseEntry(Document):

    def validate(self):
        self.calculate_totals()

    def calculate_totals(self):
        self.total_amount = 0
        self.total_vat    = 0

        for item in self.items:
            item.amount = flt(item.amount)

            if item.amount and item.vat_percentage:
                item.vat_amount = flt(item.amount * item.vat_percentage / 100)
            else:
                item.vat_amount = 0

            item.total_amount = flt(item.amount) + flt(item.vat_amount)

            self.total_amount += item.amount
            self.total_vat    += item.vat_amount

        self.grand_total = self.total_amount + self.total_vat

    def on_submit(self):
        self.make_journal_entry()
        self.db_set("status", "Paid", update_modified=False)

    def on_cancel(self):
        if not self.flags.get("ignore_linked_je_cancel") and self.journal_entry:
            je = frappe.get_doc("Journal Entry", self.journal_entry)

            if je.docstatus == 1:
                je.flags.ignore_linked_expense_cancel = True
                je.cancel()


        self.db_set("journal_entry", "", update_modified=False)
        self.db_set("status", "", update_modified=False)

    def on_trash(self):
     
        journal_entry_name = frappe.db.get_value(
            "Journal Entry", {"expense_entry": self.name}, "name"
        )

        if not journal_entry_name:
            return

        je = frappe.get_doc("Journal Entry", journal_entry_name)

        if je.docstatus == 1:
            je.flags.ignore_linked_expense_cancel = True
            je.cancel()

        frappe.delete_doc("Journal Entry", journal_entry_name, ignore_permissions=True, force=True)

    @frappe.whitelist()
    def make_journal_entry(self):

        je               = frappe.new_doc("Journal Entry")
        je.voucher_type  = "Journal Entry"
        je.company       = self.company
        je.expense_entry = self.name
        je.posting_date  = self.posting_date
        je.custom_project       = self.project
        je.remark        = f"Journal Entry for Expense Entry {self.name}"

        for row in self.items:

            je.append("accounts", {
                "account"                   : row.account,
                "debit_in_account_currency" : row.amount,
                "party_type"                : row.party_type,
                "party"                     : row.party,
                "user_remark"               : row.narration or "",
                "voucher_no"                : row.voucher_no,
     
                "trn"                       : row.trn,
                "supplier_name"             : row.supplier_name,
                "employee_name"             : row.employee_name,
            })

            if flt(row.vat_amount) > 0:
                je.append("accounts", {
                    "account"                   : row.tax_account,
                    "debit_in_account_currency" : flt(row.vat_amount),
                 
                    "user_remark"               : row.narration or "",
                })

            je.append("accounts", {
                "account"                    : row.account_from,
                "credit_in_account_currency" : flt(row.total_amount),
                "user_remark"                : row.narration or "",
               
            })

        je.insert(ignore_permissions=True)
        je.db_set("title", f"Expense Entry: {self.name}", update_modified=False)
        je.submit()

        self.db_set("journal_entry", je.name, update_modified=False)
        self.db_set("status", "Paid", update_modified=False)

        return je.name

def cancel_linked_expense_entry(doc, method=None):
    if doc.flags.get("ignore_linked_expense_cancel"):
        return

    expense_entry_name = frappe.db.get_value(
        "Expense Entry", {"journal_entry": doc.name}, "name"
    )

    if not expense_entry_name:
        return

    expense_doc = frappe.get_doc("Expense Entry", expense_entry_name)

    if expense_doc.docstatus == 1:
        expense_doc.flags.ignore_linked_je_cancel = True
        expense_doc.cancel()

    doc.db_set("expense_entry", "", update_modified=False)


def delete_linked_expense_entry(doc, method=None):
    expense_entry_name = frappe.db.get_value(
        "Expense Entry", {"journal_entry": doc.name}, "name"
    )

    if not expense_entry_name:
        return

    expense_doc = frappe.get_doc("Expense Entry", expense_entry_name)

    if expense_doc.docstatus == 1:
        expense_doc.flags.ignore_linked_je_cancel = True
        expense_doc.cancel()

    frappe.db.set_value("Expense Entry", expense_entry_name, "journal_entry", "", update_modified=False)
    frappe.delete_doc("Expense Entry", expense_entry_name, ignore_permissions=True, force=True)
# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Cash Requisition — request a cash advance for a campaign's Activities and
Other Costs. On submit it is pushed to SAP Business One as an A/P Down Payment
Request (PurchaseDownPayments, service/account based)."""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class CashRequisition(Document):
	def before_insert(self):
		if not self.requested_by:
			self.requested_by = frappe.session.user
		# Default the SAP posting fields from Agriculture Settings (set once).
		settings = frappe.get_cached_doc("Agriculture Settings")
		if not self.pay_to:
			self.pay_to = settings.get("sap_downpayment_card_code")
		if not self.expense_account:
			self.expense_account = settings.get("sap_downpayment_account")
		if not self.tax_code:
			self.tax_code = settings.get("sap_downpayment_tax_code")

	def validate(self):
		self.total_amount = sum(flt(r.amount) for r in self.items)
		if not self.items:
			frappe.throw(_("Add at least one line to the Cash Requisition."))
		if self.total_amount <= 0:
			frappe.throw(_("Total Cash Requested must be greater than zero."))

	def on_submit(self):
		settings = frappe.get_cached_doc("Agriculture Settings")
		if not settings.sap_b1_enabled:
			return
		already = frappe.db.exists("SAP B1 Sync Log", {
			"reference_doctype": "Cash Requisition",
			"reference_name": self.name,
			"sync_type": "DownPaymentRequest",
			"status": "Success",
		})
		if not already:
			self.db_set("sap_status", "Pending")
			frappe.enqueue(
				"agriculture.agriculture.sap_integration.push_cash_requisition",
				queue="long",
				requisition_name=self.name,
			)

# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Cash Requisition — request a cash advance for a campaign's Activities and
Other Costs. On submit it is pushed to SAP Business One as an A/P Down Payment
Request (PurchaseDownPayments, service/account based)."""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


def _user_supplier_code(user=None):
	"""The default SAP vendor/supplier CardCode mapped on the User record."""
	user = user or frappe.session.user
	return frappe.db.get_value("User", user, "sap_supplier_code")


class CashRequisition(Document):
	def before_insert(self):
		if not self.requested_by:
			self.requested_by = frappe.session.user
		settings = frappe.get_cached_doc("Agriculture Settings")
		# Pay To defaults from the requester's mapped supplier, then settings.
		if not self.pay_to:
			self.pay_to = _user_supplier_code(self.requested_by) or settings.get("sap_downpayment_card_code")
		# Default (fallback) expense account + tax code from settings.
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
		# Every line must resolve to a SAP expense account (its own, or the default).
		for r in self.items:
			if not (r.expense_account or self.expense_account):
				frappe.throw(_(
					"Line '{0}' has no Expense Account and no Default Expense Account is set. "
					"Set an account on the activity, on the line, or as the requisition default."
				).format(r.description or r.idx))

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

	@frappe.whitelist()
	def submit_requisition(self):
		"""Mobile entry point — submit the draft created offline (queues the SAP
		Down Payment Request)."""
		if self.docstatus == 0:
			self.submit()
		return self.name


@frappe.whitelist()
def get_cash_requisition_lines(tfop):
	"""Build cash-requisition lines from a TFOP's Activities + Other Costs,
	resolving each activity's SAP expense account from the Marketing Activity Type."""
	doc = frappe.get_doc("TFOP", tfop)
	lines = []
	for a in doc.activities:
		if not flt(a.amount):
			continue
		acct = frappe.db.get_value("Marketing Activity Type", a.activity, "expense_account") if a.activity else None
		lines.append({
			"source": "Activity",
			"description": a.activity,
			"expense_account": acct or "",
			"amount": flt(a.amount),
		})
	for o in doc.other_costs:
		if not flt(o.amount):
			continue
		lines.append({
			"source": "Other Cost",
			"description": o.cost_description,
			"expense_account": "",
			"amount": flt(o.amount),
		})
	return lines

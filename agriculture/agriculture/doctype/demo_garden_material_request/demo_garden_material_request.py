# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class DemoGardenMaterialRequest(Document):
	def validate(self):
		if not self.items:
			frappe.throw(_("Please add at least one material to the request"))

	@frappe.whitelist()
	def submit_request(self):
		if self.status != "Draft":
			frappe.throw(_("Only Draft requests can be submitted"))
		frappe.db.set_value("Demo Garden Material Request", self.name, "status", "Submitted")
		frappe.db.set_value("Demo Garden", self.demo_garden, "status", "Material Requested")
		self._notify_supervisor()
		self.status = "Submitted"
		self._trigger_sap_sync()
		return "Submitted"

	@frappe.whitelist()
	def approve_request(self):
		if self.status != "Submitted":
			frappe.throw(_("Only Submitted requests can be approved"))
		frappe.db.set_value("Demo Garden Material Request", self.name, {
			"status": "Approved",
			"approved_by": frappe.session.user,
			"approval_date": today(),
		})
		frappe.db.commit()
		return "Approved"

	@frappe.whitelist()
	def reject_request(self, reason=""):
		frappe.db.set_value("Demo Garden Material Request", self.name, {
			"status": "Rejected",
			"rejection_reason": reason,
		})
		return "Rejected"

	@frappe.whitelist()
	def mark_issued(self):
		if self.status != "Approved":
			frappe.throw(_("Request must be Approved before marking as Issued"))
		frappe.db.set_value("Demo Garden Material Request", self.name, {
			"status": "Issued",
			"issued_by": frappe.session.user,
			"issue_date": today(),
		})
		frappe.db.commit()
		self.status = "Issued"
		self.issue_date = today()
		self._trigger_sap_sync()
		return "Issued"

	@frappe.whitelist()
	def confirm_receipt(self):
		if self.status != "Issued":
			frappe.throw(_("Materials must be Issued before confirming receipt"))
		frappe.db.set_value("Demo Garden Material Request", self.name, {
			"status": "Received",
			"promoter_receipt_confirmed": 1,
			"promoter_receipt_date": today(),
		})
		frappe.db.set_value("Demo Garden", self.demo_garden, "status", "Material Received")
		frappe.db.commit()
		self._post_receipt_to_ledger()
		self.status = "Received"
		self.promoter_receipt_date = today()
		self._trigger_sap_sync()
		return "Received"

	def _post_receipt_to_ledger(self):
		"""Post each received material to the Promoter Stock Ledger."""
		from agriculture.agriculture.doctype.demo_garden_planting_record.demo_garden_planting_record import (
			_post_ledger_entry,
		)
		receipt_date = frappe.db.get_value(
			"Demo Garden Material Request", self.name, "promoter_receipt_date"
		) or today()
		for item in self.items:
			qty = item.quantity_received or item.quantity_issued or item.quantity_requested or 0
			if not qty:
				continue
			_post_ledger_entry(
				promoter=self.promoter,
				demo_garden=self.demo_garden,
				transaction_type="Receipt",
				transaction_date=receipt_date,
				product_name=item.item_name,
				uom=item.uom,
				qty_in=qty,
				reference_doctype="Demo Garden Material Request",
				reference_name=self.name,
			)

	def _trigger_sap_sync(self):
		"""Invoke the SAP B1 auto-push hook explicitly.

		Status transitions in this controller use frappe.db.set_value, which
		bypasses the on_update doc-event the SAP hook is wired to in hooks.py.
		Calling it directly (with self.status already updated in-memory) ensures
		the Stock Transfer Request / Goods Issue / Goods Receipt push fires.
		The hook itself no-ops when SAP B1 is disabled and is idempotent.
		"""
		from agriculture.agriculture.sap_integration import on_material_request_update
		on_material_request_update(self)

	def _notify_supervisor(self):
		promoter = frappe.get_doc("Field Promoter", self.promoter)
		if not promoter.supervisor:
			return
		supervisor_user = frappe.db.get_value("Field Promoter", promoter.supervisor, "user")
		if not supervisor_user:
			return
		frappe.sendmail(
			recipients=[supervisor_user],
			subject=_("Material Request Awaiting Approval: {0}").format(self.name),
			message=_(
				"Field Promoter {0} has submitted Material Request {1} for Demo Garden {2}."
			).format(promoter.promoter_name, self.name, self.demo_garden),
		)

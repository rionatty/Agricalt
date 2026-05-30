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
		return "Received"

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

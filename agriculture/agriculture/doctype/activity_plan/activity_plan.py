# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class ActivityPlan(Document):
	def validate(self):
		self.validate_dates()

	def validate_dates(self):
		if self.from_date and self.to_date and self.from_date > self.to_date:
			frappe.throw(_("To Date must be after From Date"))

	@frappe.whitelist()
	def submit_for_approval(self):
		if self.status != "Draft":
			frappe.throw(_("Only Draft plans can be submitted for approval"))
		frappe.db.set_value("Activity Plan", self.name, "status", "Submitted")
		self.notify_supervisor()
		return "Submitted"

	@frappe.whitelist()
	def approve(self):
		if self.status != "Submitted":
			frappe.throw(_("Only Submitted plans can be approved"))
		frappe.db.set_value("Activity Plan", self.name, {
			"status": "Approved",
			"approved_by": frappe.session.user,
			"approval_date": today(),
		})
		frappe.db.commit()
		return "Approved"

	@frappe.whitelist()
	def reject(self, reason=""):
		if self.status not in ("Submitted", "Draft"):
			frappe.throw(_("Only Submitted plans can be rejected"))
		frappe.db.set_value("Activity Plan", self.name, {
			"status": "Rejected",
			"rejection_reason": reason,
		})
		return "Rejected"

	def notify_supervisor(self):
		"""Send email notification to the promoter's supervisor."""
		promoter = frappe.get_doc("Field Promoter", self.promoter)
		if not promoter.supervisor:
			return
		supervisor_user = frappe.db.get_value("Field Promoter", promoter.supervisor, "user")
		if not supervisor_user:
			return
		frappe.sendmail(
			recipients=[supervisor_user],
			subject=_("Activity Plan Submitted for Approval: {0}").format(self.name),
			message=_(
				"Field Promoter {0} has submitted Activity Plan {1} ({2} to {3}) for your approval."
			).format(promoter.promoter_name, self.name, self.from_date, self.to_date),
		)

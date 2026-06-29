# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Marketing Material Request — request branded/marketing materials for a campaign.

On submit it is pushed to SAP Business One as a Stock Transfer Request
(from_warehouse -> to_warehouse), reusing the existing SAP integration.
"""
import frappe
from frappe.model.document import Document


class MarketingMaterialRequest(Document):
	def before_insert(self):
		if not self.requested_by:
			self.requested_by = frappe.session.user

	def on_submit(self):
		settings = frappe.get_cached_doc("Agriculture Settings")
		if not settings.sap_b1_enabled:
			return
		already = frappe.db.exists("SAP B1 Sync Log", {
			"reference_doctype": "Marketing Material Request",
			"reference_name": self.name,
			"sync_type": "StockTransferRequest",
			"status": "Success",
		})
		if not already:
			self.db_set("sap_status", "Pending")
			frappe.enqueue(
				"agriculture.agriculture.sap_integration.push_marketing_material_request",
				queue="long",
				request_name=self.name,
			)

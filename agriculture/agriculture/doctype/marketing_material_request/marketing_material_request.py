# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Marketing Material Request — request branded/marketing materials for a campaign.

On submit it is pushed to SAP Business One as a Stock Transfer Request
(from_warehouse -> to_warehouse), reusing the existing SAP integration.
"""
import frappe
from frappe import _
from frappe.model.document import Document


class MarketingMaterialRequest(Document):
	def before_insert(self):
		if not self.requested_by:
			self.requested_by = frappe.session.user
		# Materials ship FROM the central source store TO the requester's own warehouse.
		if not self.to_warehouse:
			from agriculture.agriculture.sap_integration import _get_user_default_warehouse
			self.to_warehouse = _get_user_default_warehouse(self.requested_by)
		if not self.from_warehouse:
			self.from_warehouse = frappe.db.get_single_value(
				"Agriculture Settings", "default_source_warehouse"
			)

	def validate(self):
		# A transfer must move stock between two different warehouses.
		# (SAP-code-level collisions are caught later, after resolution, in the push.)
		if not self.from_warehouse:
			frappe.throw(_("From Warehouse is required."))
		if not self.to_warehouse:
			frappe.throw(_("To Warehouse is required."))
		if self.from_warehouse == self.to_warehouse:
			frappe.throw(_("From Warehouse and To Warehouse cannot be the same."))

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

	@frappe.whitelist()
	def submit_mmr(self):
		"""Mobile entry point — submit the draft created offline (queues the SAP
		transfer request)."""
		if self.docstatus == 0:
			self.submit()
		return self.name

# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FieldPromoter(Document):
	def after_insert(self):
		self._create_promoter_warehouse()

	def _create_promoter_warehouse(self):
		"""
		Auto-create an ERPNext Warehouse for this promoter when they are registered.
		The warehouse tracks demo materials issued to / held by this promoter.
		"""
		warehouse_name = f"{self.promoter_name} - Promoter Store"
		if frappe.db.exists("Warehouse", {"warehouse_name": warehouse_name}):
			existing = frappe.db.get_value("Warehouse", {"warehouse_name": warehouse_name}, "name")
			frappe.db.set_value("Field Promoter", self.name, "promoter_warehouse", existing)
			return

		try:
			company = (
				frappe.db.get_single_value("Global Defaults", "default_company")
				or frappe.db.get_value("Company", {}, "name")
				or ""
			)
			parent_warehouse = frappe.db.get_value(
				"Warehouse", {"is_group": 1, "company": company}, "name"
			) or "All Warehouses"

			doc = frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": warehouse_name,
				"parent_warehouse": parent_warehouse,
				"company": company,
				"warehouse_type": "Transit",
				"is_group": 0,
			})
			doc.flags.ignore_permissions = True
			doc.insert()
			frappe.db.set_value("Field Promoter", self.name, "promoter_warehouse", doc.name)
			frappe.db.commit()
		except Exception as e:
			# Non-fatal — warehouse creation failure should not block promoter save
			frappe.log_error(
				f"Could not create warehouse for promoter {self.name}: {e}",
				"Promoter Warehouse Creation"
			)

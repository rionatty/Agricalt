# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class OrderCollection(Document):
	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		total = 0
		for item in self.items:
			item.total_value = (item.quantity or 0) * (item.unit_price or 0)
			total += item.total_value
		self.total_order_value = total

	@frappe.whitelist()
	def submit_order(self):
		if self.status != "Draft":
			frappe.throw(_("Only Draft orders can be submitted"))
		frappe.db.set_value("Order Collection", self.name, "status", "Submitted")
		return "Submitted"

	@frappe.whitelist()
	def get_promoter_orders_summary(promoter, from_date, to_date):
		"""Return total orders collected by a promoter in a date range."""
		orders = frappe.get_all(
			"Order Collection",
			filters={
				"promoter": promoter,
				"collection_date": ["between", [from_date, to_date]],
				"status": ["in", ["Submitted", "Processed in ERP"]],
			},
			fields=["name", "total_order_value", "payment_amount", "stockist"],
		)
		return {
			"total_orders": len(orders),
			"total_value": sum(o.total_order_value or 0 for o in orders),
			"total_payments": sum(o.payment_amount or 0 for o in orders),
			"orders": orders,
		}

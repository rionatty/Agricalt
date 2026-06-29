# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Channel Stock Movement — record stock moving from one channel partner
(Customer) to another and post it as an ERPNext Stock Entry (Material Transfer)
between the two customers' warehouses, so channel stock holding stays accurate.
"""
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ChannelStockMovement(Document):
	def validate(self):
		# Resolve each customer's warehouse (fetch_from fills the UI; make sure
		# the server has them too, e.g. for API-created docs).
		if not self.from_warehouse and self.from_customer:
			self.from_warehouse = frappe.db.get_value("Customer", self.from_customer, "crm_warehouse")
		if not self.to_warehouse and self.to_customer:
			self.to_warehouse = frappe.db.get_value("Customer", self.to_customer, "crm_warehouse")

		if not self.from_warehouse:
			frappe.throw(_("From Customer '{0}' has no CRM Warehouse yet.").format(self.from_customer))
		if not self.to_warehouse:
			frappe.throw(_("To Customer '{0}' has no CRM Warehouse yet.").format(self.to_customer))
		if self.from_customer == self.to_customer or self.from_warehouse == self.to_warehouse:
			frappe.throw(_("From and To must be two different customers / warehouses."))

		self.total_qty = sum(flt(r.qty) for r in self.items)
		if not self.items or self.total_qty <= 0:
			frappe.throw(_("Add at least one item with a positive quantity."))

	def on_submit(self):
		company = frappe.db.get_value("Warehouse", self.from_warehouse, "company")
		items = []
		for r in self.items:
			if not r.item or flt(r.qty) <= 0:
				continue
			items.append({
				"item_code": r.item,
				"qty": flt(r.qty),
				"uom": r.uom or frappe.db.get_value("Item", r.item, "stock_uom") or "Nos",
				"s_warehouse": self.from_warehouse,
				"t_warehouse": self.to_warehouse,
			})
		if not items:
			frappe.throw(_("Nothing to move."))

		se = frappe.get_doc({
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Transfer",
			"company": company,
			"posting_date": self.movement_date,
			"set_posting_time": 1,
			"remarks": f"Channel Stock Movement {self.name}: {self.from_customer} -> {self.to_customer}",
			"items": items,
		})
		se.insert(ignore_permissions=True)
		se.submit()
		self.db_set("stock_entry", se.name)

	def on_cancel(self):
		# Reverse the stock move by cancelling the linked Material Transfer.
		if self.stock_entry and frappe.db.exists("Stock Entry", self.stock_entry):
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.flags.ignore_permissions = True
				se.cancel()
		self.db_set("stock_entry", None)

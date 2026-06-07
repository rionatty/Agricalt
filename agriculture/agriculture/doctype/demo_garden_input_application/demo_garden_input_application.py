# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from agriculture.agriculture.doctype.demo_garden_planting_record.demo_garden_planting_record import (
	_post_ledger_entry,
	get_consumed_qty,
)


class DemoGardenInputApplication(Document):
	def validate(self):
		self.validate_stock_available()

	def validate_stock_available(self):
		"""Ensure the promoter has received the inputs they are trying to apply."""
		received = self._get_received_inputs()
		consumed = get_consumed_qty(self.demo_garden, self.doctype, self.name)
		errors = []
		for row in self.inputs:
			key = (row.product_name or "").strip().lower()
			available = received.get(key, 0) - consumed.get(key, 0)
			row.quantity_available = available
			if row.quantity_applied > available:
				errors.append(
					_("Row {0}: Cannot apply {1} {2} of '{3}' — only {4} received from store.").format(
						row.idx, row.quantity_applied, row.uom or "", row.product_name, available
					)
				)
		if errors:
			frappe.throw("\n".join(errors), title=_("Insufficient Stock"))

	def _get_received_inputs(self):
		"""Return {product_name_lower: qty_received} for chemicals/inputs on this demo garden."""
		received = {}
		requests = frappe.get_all(
			"Demo Garden Material Request",
			filters={"demo_garden": self.demo_garden, "status": "Received"},
			fields=["name"],
		)
		for req in requests:
			items = frappe.get_all(
				"Demo Garden Material Item",
				filters={"parent": req.name, "item_type": ["in", ["Chemical", "Fertilizer", "Other"]]},
				fields=["item_name", "quantity_received"],
			)
			for item in items:
				key = (item.item_name or "").strip().lower()
				received[key] = received.get(key, 0) + (item.quantity_received or 0)
		return received

	@frappe.whitelist()
	def submit_application(self):
		if self.status != "Draft":
			frappe.throw(_("Only Draft applications can be submitted"))

		frappe.db.set_value("Demo Garden Input Application", self.name, "status", "Submitted")

		# Update demo garden status if still on Planted
		current_status = frappe.db.get_value("Demo Garden", self.demo_garden, "status")
		if current_status == "Planted":
			frappe.db.set_value("Demo Garden", self.demo_garden, "status", "Monitoring")

		# Post consumption to stock ledger
		for row in self.inputs:
			if not row.quantity_applied:
				continue
			_post_ledger_entry(
				promoter=self.promoter,
				demo_garden=self.demo_garden,
				transaction_type="Input Application",
				transaction_date=self.application_date,
				product_name=row.product_name,
				uom=row.uom,
				qty_out=row.quantity_applied,
				reference_doctype="Demo Garden Input Application",
				reference_name=self.name,
			)
		return "Submitted"

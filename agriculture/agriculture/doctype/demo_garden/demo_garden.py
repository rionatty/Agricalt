# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, today


class DemoGarden(Document):
	def validate(self):
		self.calculate_expected_harvest_date()

	def calculate_expected_harvest_date(self):
		"""Auto-calculate expected harvest date from planting date + max crop maturity."""
		if not self.planting_date or not self.products:
			return
		max_duration = max(
			(p.crop_maturity_duration or 0) for p in self.products
		)
		if max_duration:
			self.expected_harvest_date = add_days(self.planting_date, max_duration)

	def update_status(self):
		"""Derive status from lifecycle data; called by child transactions."""
		if self.completion_date:
			self.status = "Completed"
		elif self.field_day_date:
			self.status = "Field Day Done"
		elif self.planting_date:
			self.status = "Planted"
		frappe.db.set_value("Demo Garden", self.name, "status", self.status)

	@frappe.whitelist()
	def mark_material_received(self):
		if self.status == "Material Requested":
			frappe.db.set_value("Demo Garden", self.name, "status", "Material Received")
			return "Material Received"

	@frappe.whitelist()
	def get_pending_material_requests(self):
		return frappe.get_all(
			"Demo Garden Material Request",
			filters={"demo_garden": self.name, "status": ["not in", ["Received", "Rejected"]]},
			fields=["name", "status", "request_date", "promoter"],
		)

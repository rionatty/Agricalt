# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class DemoGardenFieldDay(Document):
	def validate(self):
		self.validate_demo_garden_exists()

	def validate_demo_garden_exists(self):
		"""Ensure the linked demo garden is in a state that allows a field day."""
		if not self.demo_garden:
			return
		status = frappe.db.get_value("Demo Garden", self.demo_garden, "status")
		if status not in ("Planted", "Monitoring", "Field Day Scheduled", "Material Received"):
			frappe.throw(
				_("Demo Garden {0} must be in Planted or Monitoring state before recording a Field Day. Current status: {1}").format(
					self.demo_garden, status
				)
			)

	def on_submit(self):
		"""Mark demo garden as Field Day Done on field day submission."""
		frappe.db.set_value("Demo Garden", self.demo_garden, {
			"status": "Field Day Done",
			"field_day_date": self.field_day_date,
		})

	@frappe.whitelist()
	def mark_complete(self):
		frappe.db.set_value("Demo Garden Field Day", self.name, "status", "Completed")
		frappe.db.set_value("Demo Garden", self.demo_garden, {
			"status": "Completed",
			"completion_date": today(),
		})
		return "Completed"

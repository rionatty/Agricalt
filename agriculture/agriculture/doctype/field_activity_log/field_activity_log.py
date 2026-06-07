# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FieldActivityLog(Document):
	def validate(self):
		self.set_gps_location_text()
		self.validate_photos()

	def set_gps_location_text(self):
		if self.gps_latitude and self.gps_longitude:
			self.gps_location_text = f"{self.gps_latitude:.6f}, {self.gps_longitude:.6f}"

	def validate_photos(self):
		"""Set GPS text on each photo row."""
		for photo in self.photos:
			if photo.gps_latitude and photo.gps_longitude:
				photo.gps_location_text = f"{photo.gps_latitude:.6f}, {photo.gps_longitude:.6f}"

	@frappe.whitelist()
	def submit_activity(self):
		if self.status != "Draft":
			frappe.throw(_("Only Draft activities can be submitted"))
		frappe.db.set_value("Field Activity Log", self.name, "status", "Submitted")
		self.status = "Submitted"
		self._link_to_activity_plan()
		return "Submitted"

	def _link_to_activity_plan(self):
		"""If this activity matches an approved planned activity, link them and
		mark the corresponding Activity Plan Item as executed."""
		from agriculture.agriculture.doctype.activity_plan.activity_plan import link_activity_to_plan
		plan = link_activity_to_plan(self)
		if plan:
			frappe.db.set_value("Field Activity Log", self.name,
				{"activity_plan": plan, "is_planned": 1})

	@frappe.whitelist()
	def get_promoter_summary(promoter, from_date, to_date):
		"""Return KPI counts for a promoter within a date range."""
		filters = {"promoter": promoter, "activity_date": ["between", [from_date, to_date]]}
		all_logs = frappe.get_all("Field Activity Log", filters=filters, fields=["activity_type"])
		summary = {
			"Farm Visit": 0, "Stockist Visit": 0, "Exhibition": 0,
			"Farmer Training": 0, "Demo Garden Visit": 0, "Payment Collection": 0,
		}
		for log in all_logs:
			if log.activity_type in summary:
				summary[log.activity_type] += 1
		return summary

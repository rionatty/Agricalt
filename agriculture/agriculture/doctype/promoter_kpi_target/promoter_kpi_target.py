# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PromoterKPITarget(Document):
	def validate(self):
		if self.from_date and self.to_date and self.from_date > self.to_date:
			frappe.throw(_("To Date must be after From Date"))


def get_targets_for(promoter, on_date=None):
	"""
	Return the active KPI target for a promoter on a given date.
	Falls back to the defaults defined in Agriculture Settings.
	"""
	on_date = on_date or frappe.utils.today()
	rows = frappe.get_all(
		"Promoter KPI Target",
		filters={
			"promoter": promoter,
			"status": "Active",
			"from_date": ["<=", on_date],
			"to_date": [">=", on_date],
		},
		fields=["*"],
		limit=1,
	)
	if rows:
		return rows[0]

	# Fall back to settings defaults
	s = frappe.get_cached_doc("Agriculture Settings")
	return {
		"target_farm_visits": s.default_target_farm_visits or 0,
		"target_demo_gardens": s.default_target_demo_gardens or 0,
		"target_trainings": s.default_target_trainings or 0,
		"target_exhibitions": s.default_target_exhibitions or 0,
		"target_stockist_visits": s.default_target_stockist_visits or 0,
		"target_orders_value": s.default_target_orders_value or 0,
	}

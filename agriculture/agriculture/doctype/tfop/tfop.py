# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""TFOP — Twiga Farmers Outreach Program (Marketing budget document).

A season-long campaign budget. Holds projected Products, Activities, Marketing
Material and Other Costs; rolls them up into a total campaign budget; and tracks
actual spend posted via TFOP Actual records (budget vs actuals).
Approval is driven by the "TFOP Approval" Frappe Workflow (FOM -> GM -> Finance).
"""
import frappe
from frappe.model.document import Document
from frappe.utils import flt


class TFOP(Document):
	def before_insert(self):
		# Sector specialist defaults to the logged-in user (server-side fallback;
		# the client script sets it on the new form too).
		if not self.sector_specialist:
			self.sector_specialist = frappe.session.user

	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		"""Compute per-line totals, per-table totals, the campaign budget, and
		the live budget-vs-actual variance."""
		total_products = 0.0
		for row in self.products:
			row.line_total = flt(row.qty) * flt(row.sales_price)
			total_products += row.line_total
		self.total_product_cost = total_products

		total_activities = 0.0
		for row in self.activities:
			row.amount = flt(row.units) * flt(row.rate)
			total_activities += row.amount
		self.total_activity_cost = total_activities

		total_materials = 0.0
		for row in self.marketing_materials:
			row.amount = flt(row.qty) * flt(row.rate)
			total_materials += row.amount
		self.total_material_cost = total_materials

		total_other = sum(flt(row.amount) for row in self.other_costs)
		self.total_other_cost = total_other

		self.total_campaign_cost = (
			total_products + total_activities + total_materials + total_other
		)
		self._set_variance(flt(self.total_actual_cost))

	def _set_variance(self, actual):
		budget = flt(self.total_campaign_cost)
		self.budget_variance = budget - flt(actual)
		self.budget_utilisation_pct = (flt(actual) / budget * 100.0) if budget else 0.0

	def recalc_actuals(self):
		"""Re-sum submitted TFOP Actual postings against this campaign and store
		the actual total + variance. Called from TFOP Actual on submit/cancel."""
		actual = frappe.db.get_value(
			"TFOP Actual",
			{"tfop": self.name, "docstatus": 1},
			"coalesce(sum(amount), 0)",
		) or 0
		self.db_set("total_actual_cost", flt(actual))
		self.db_set("budget_variance", flt(self.total_campaign_cost) - flt(actual))
		self.db_set(
			"budget_utilisation_pct",
			(flt(actual) / flt(self.total_campaign_cost) * 100.0)
			if flt(self.total_campaign_cost) else 0.0,
		)

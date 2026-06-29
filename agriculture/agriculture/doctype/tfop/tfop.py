# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""TFOP — Twiga Farmers Outreach Program (Marketing budget document).

Holds projected Products, Activities, Marketing Material and Other Costs; rolls
them into a campaign budget; and tracks cumulative actual spend per budget line
from submitted TFOP Actual postings (budget vs actuals, per line and in total).
Approval is driven by the "TFOP Approval" Frappe Workflow (FOM -> GM -> Finance).
"""
import frappe
from frappe.model.document import Document
from frappe.utils import flt

# cost_category -> (child table fieldname, child doctype, row field identifying the line)
_LINE_MAP = {
	"Products": ("products", "TFOP Product", "item_code"),
	"Activities": ("activities", "TFOP Activity", "activity"),
	"Marketing Material": ("marketing_materials", "TFOP Marketing Material", "item"),
	"Other Cost": ("other_costs", "TFOP Other Cost", "budget_category"),
}


class TFOP(Document):
	def before_insert(self):
		if not self.sector_specialist:
			self.sector_specialist = frappe.session.user

	def validate(self):
		self.calculate_totals()

	@staticmethod
	def _budget_of(table, row):
		if table == "products":
			return flt(row.qty) * flt(row.sales_price)
		if table == "activities":
			return flt(row.units) * flt(row.rate)
		if table == "marketing_materials":
			return flt(row.qty) * flt(row.rate)
		return flt(row.amount)  # other_costs

	def calculate_totals(self):
		"""Recompute per-line budgets + variance and the campaign budget. Actual
		figures are whatever recalc_actuals last stored on the rows."""
		tp = 0.0
		for r in self.products:
			r.line_total = flt(r.qty) * flt(r.sales_price)
			r.variance = r.line_total - flt(r.actual_amount)
			tp += r.line_total
		self.total_product_cost = tp

		ta = 0.0
		for r in self.activities:
			r.amount = flt(r.units) * flt(r.rate)
			r.variance = r.amount - flt(r.actual_amount)
			ta += r.amount
		self.total_activity_cost = ta

		tm = 0.0
		for r in self.marketing_materials:
			r.amount = flt(r.qty) * flt(r.rate)
			r.variance = r.amount - flt(r.actual_amount)
			tm += r.amount
		self.total_material_cost = tm

		to = 0.0
		for r in self.other_costs:
			r.variance = flt(r.amount) - flt(r.actual_amount)
			to += flt(r.amount)
		self.total_other_cost = to

		self.total_campaign_cost = tp + ta + tm + to

		self.total_product_actual = sum(flt(r.actual_amount) for r in self.products)
		self.total_activity_actual = sum(flt(r.actual_amount) for r in self.activities)
		self.total_material_actual = sum(flt(r.actual_amount) for r in self.marketing_materials)
		self.total_other_actual = sum(flt(r.actual_amount) for r in self.other_costs)
		self.total_actual_cost = (
			self.total_product_actual + self.total_activity_actual
			+ self.total_material_actual + self.total_other_actual
		)
		self._set_variance(self.total_actual_cost)

	def _set_variance(self, actual):
		budget = flt(self.total_campaign_cost)
		self.budget_variance = budget - flt(actual)
		self.budget_utilisation_pct = (flt(actual) / budget * 100.0) if budget else 0.0

	def recalc_actuals(self):
		"""Recompute cumulative actuals per budget line from submitted TFOP Actual
		postings, then roll up per-table + campaign totals. Called from TFOP Actual
		on submit/cancel (parent is loaded fresh, so it writes via db.set_value)."""
		postings = frappe.get_all(
			"TFOP Actual",
			filters={"tfop": self.name, "docstatus": 1},
			fields=["cost_category", "against", "amount"],
		)
		acc = {}
		for p in postings:
			acc[(p.cost_category, p.against or "")] = (
				acc.get((p.cost_category, p.against or ""), 0.0) + flt(p.amount)
			)

		subtotal = {"products": 0.0, "activities": 0.0, "marketing_materials": 0.0, "other_costs": 0.0}
		for category, (table, child_dt, keyfield) in _LINE_MAP.items():
			for row in self.get(table):
				actual = acc.get((category, row.get(keyfield) or ""), 0.0)
				budget = self._budget_of(table, row)
				frappe.db.set_value(
					child_dt, row.name,
					{"actual_amount": actual, "variance": budget - actual},
					update_modified=False,
				)
				subtotal[table] += actual

		total_actual = sum(flt(p.amount) for p in postings)
		budget = flt(self.total_campaign_cost)
		self.db_set("total_product_actual", subtotal["products"])
		self.db_set("total_activity_actual", subtotal["activities"])
		self.db_set("total_material_actual", subtotal["marketing_materials"])
		self.db_set("total_other_actual", subtotal["other_costs"])
		self.db_set("total_actual_cost", total_actual)
		self.db_set("budget_variance", budget - total_actual)
		self.db_set("budget_utilisation_pct", (total_actual / budget * 100.0) if budget else 0.0)

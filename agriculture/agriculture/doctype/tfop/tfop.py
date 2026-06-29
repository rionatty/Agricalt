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
	"Other Cost": ("other_costs", "TFOP Other Cost", "cost_description"),
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
		"""Recompute cumulative actuals per budget line by summing the actual lines
		of every submitted TFOP Actual document for this campaign, then roll up
		per-table + campaign totals. Called from TFOP Actual on submit/cancel."""
		def summed(actual_child_dt, keyfield):
			rows = frappe.db.sql(
				f"""
				select c.`{keyfield}` as k, coalesce(sum(c.actual_amount), 0) as amt
				from `tab{actual_child_dt}` c
				inner join `tabTFOP Actual` p on p.name = c.parent
				where p.tfop = %s and p.docstatus = 1
				group by c.`{keyfield}`
				""",
				self.name, as_dict=True,
			)
			return {(r.k or ""): flt(r.amt) for r in rows}

		acc = {
			"products": summed("TFOP Actual Product", "item_code"),
			"activities": summed("TFOP Actual Activity", "activity"),
			"marketing_materials": summed("TFOP Actual Marketing Material", "item"),
			"other_costs": summed("TFOP Actual Other Cost", "cost_description"),
		}

		for category, (table, child_dt, keyfield) in _LINE_MAP.items():
			line_acc = acc[table]
			for row in self.get(table):
				actual = line_acc.get(row.get(keyfield) or "", 0.0)
				budget = self._budget_of(table, row)
				frappe.db.set_value(
					child_dt, row.name,
					{"actual_amount": actual, "variance": budget - actual},
					update_modified=False,
				)

		subtotal = {table: sum(vals.values()) for table, vals in acc.items()}
		total_actual = sum(subtotal.values())
		budget = flt(self.total_campaign_cost)
		self.db_set("total_product_actual", subtotal["products"])
		self.db_set("total_activity_actual", subtotal["activities"])
		self.db_set("total_material_actual", subtotal["marketing_materials"])
		self.db_set("total_other_actual", subtotal["other_costs"])
		self.db_set("total_actual_cost", total_actual)
		self.db_set("budget_variance", budget - total_actual)
		self.db_set("budget_utilisation_pct", (total_actual / budget * 100.0) if budget else 0.0)

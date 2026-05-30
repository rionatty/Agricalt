# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, today


class DemoGardenPlantingRecord(Document):
	def validate(self):
		self.validate_materials_received()
		self.calculate_harvest_dates()

	def validate_materials_received(self):
		"""
		Enforce: promoter cannot record planting of a product they have not received.
		Checks against confirmed Demo Garden Material Requests for this garden.
		"""
		# Get all received materials for this demo garden
		received = self._get_received_materials()

		errors = []
		for row in self.products:
			key = (row.product_name or "").strip().lower()
			available = received.get(key, 0)
			row.quantity_available = available
			if row.quantity_planted > available:
				errors.append(
					_("Row {0}: Cannot plant {1} {2} of '{3}' — only {4} received from store.").format(
						row.idx, row.quantity_planted, row.uom or "", row.product_name, available
					)
				)
		if errors:
			frappe.throw("\n".join(errors), title=_("Stock Validation Failed"))

		self.stock_validated = 1
		self.validation_notes = f"Validated against received materials on {today()}"

	def _get_received_materials(self):
		"""Return dict of {product_name_lower: qty_received} for this demo garden."""
		received = {}
		requests = frappe.get_all(
			"Demo Garden Material Request",
			filters={"demo_garden": self.demo_garden, "status": "Received"},
			fields=["name"],
		)
		for req in requests:
			items = frappe.get_all(
				"Demo Garden Material Item",
				filters={"parent": req.name},
				fields=["item_name", "quantity_received"],
			)
			for item in items:
				key = (item.item_name or "").strip().lower()
				received[key] = received.get(key, 0) + (item.quantity_received or 0)
		return received

	def calculate_harvest_dates(self):
		"""Auto-calculate expected harvest date per product and overall."""
		max_days = 0
		for row in self.products:
			if row.crop_maturity_duration and self.planting_date:
				row.expected_harvest_date = add_days(self.planting_date, row.crop_maturity_duration)
				if row.crop_maturity_duration > max_days:
					max_days = row.crop_maturity_duration
		if max_days and self.planting_date:
			self.overall_expected_harvest_date = add_days(self.planting_date, max_days)

	@frappe.whitelist()
	def submit_planting(self):
		if self.status != "Draft":
			frappe.throw(_("Only Draft planting records can be submitted"))
		if not self.stock_validated:
			frappe.throw(_("Stock must be validated before submitting"))

		frappe.db.set_value("Demo Garden Planting Record", self.name, "status", "Submitted")

		# Update the Demo Garden
		frappe.db.set_value("Demo Garden", self.demo_garden, {
			"status": "Planted",
			"planting_date": self.planting_date,
			"expected_harvest_date": self.overall_expected_harvest_date,
		})

		# Post to Promoter Stock Ledger
		self._post_consumption_to_ledger()
		return "Submitted"

	def _post_consumption_to_ledger(self):
		"""Deduct planted quantities from promoter stock ledger."""
		for row in self.products:
			if not row.quantity_planted:
				continue
			_post_ledger_entry(
				promoter=self.promoter,
				demo_garden=self.demo_garden,
				transaction_type="Planting Consumption",
				transaction_date=self.planting_date,
				product_name=row.product_name,
				uom=row.uom,
				qty_out=row.quantity_planted,
				reference_doctype="Demo Garden Planting Record",
				reference_name=self.name,
			)


def _post_ledger_entry(promoter, demo_garden, transaction_type, transaction_date,
                       product_name, uom, qty_in=0, qty_out=0,
                       reference_doctype="", reference_name=""):
	"""Create a Promoter Stock Ledger entry and calculate running balance."""
	# Get last balance for this promoter + product
	last = frappe.get_all(
		"Promoter Stock Ledger",
		filters={"promoter": promoter, "product_name": product_name},
		fields=["balance_qty"],
		order_by="transaction_date desc, creation desc",
		limit=1,
	)
	prev_balance = last[0].balance_qty if last else 0
	new_balance = prev_balance + qty_in - qty_out

	doc = frappe.get_doc({
		"doctype": "Promoter Stock Ledger",
		"promoter": promoter,
		"transaction_date": transaction_date,
		"transaction_type": transaction_type,
		"demo_garden": demo_garden,
		"product_name": product_name,
		"uom": uom,
		"qty_in": qty_in,
		"qty_out": qty_out,
		"balance_qty": new_balance,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
	})
	doc.flags.ignore_permissions = True
	doc.insert()

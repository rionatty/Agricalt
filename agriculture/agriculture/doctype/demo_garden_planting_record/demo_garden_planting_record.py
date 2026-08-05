# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, today


class DemoGardenPlantingRecord(Document):
	def validate(self):
		self.calculate_harvest_dates()
		# Populate available quantities (informational only on save — hard block only on submit)
		self._populate_available_quantities()

	def _populate_available_quantities(self):
		"""Fill quantity_available for each row so the user can see what's in stock."""
		received = self._get_received_materials()
		consumed = get_consumed_qty(self.demo_garden, self.doctype, self.name)
		has_any_received = bool(received)
		all_ok = True
		notes = []
		for row in self.products:
			key = (row.product_name or "").strip().lower()
			available = received.get(key, 0) - consumed.get(key, 0)
			row.quantity_available = available
			if row.quantity_planted and row.quantity_planted > available:
				all_ok = False
				notes.append(
					_("'{0}': planted {1} but only {2} received.").format(
						row.product_name, row.quantity_planted, available
					)
				)

		if has_any_received and all_ok:
			self.stock_validated = 1
			self.validation_notes = f"Validated against received materials on {today()}"
		elif notes:
			self.stock_validated = 0
			self.validation_notes = "; ".join(notes)

	def validate_materials_received(self):
		"""
		Hard validation — only called on submit.
		Throws if planted quantities exceed received quantities.
		"""
		received = self._get_received_materials()
		# If no material requests exist yet, skip the hard block (allow offline/field use)
		if not received:
			frappe.msgprint(
				_("No received material requests found. Planting record saved without stock validation."),
				indicator="orange", alert=True
			)
			return

		consumed = get_consumed_qty(self.demo_garden, self.doctype, self.name)
		errors = []
		for row in self.products:
			key = (row.product_name or "").strip().lower()
			available = received.get(key, 0) - consumed.get(key, 0)
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
		# Run hard stock validation on submit
		self.validate_materials_received()

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


def get_consumed_qty(demo_garden, exclude_ref_doctype=None, exclude_ref_name=None):
	"""Return {product_name_lower: total qty_out} already consumed for a demo garden.

	Reads the Promoter Stock Ledger so stock validation nets out prior
	consumption (planting + input applications) instead of comparing against
	gross received quantities — this prevents the same receipt being spent
	twice across multiple planting records / input applications.

	A document can be excluded (by reference) so it never validates against its
	own previously-posted ledger entries when it is re-saved after submission.
	"""
	if not demo_garden:
		return {}
	entries = frappe.get_all(
		"Promoter Stock Ledger",
		filters={"demo_garden": demo_garden},
		fields=["product_name", "qty_out", "reference_doctype", "reference_name"],
	)
	consumed = {}
	for e in entries:
		if (exclude_ref_doctype and e.reference_doctype == exclude_ref_doctype
				and e.reference_name == exclude_ref_name):
			continue
		key = (e.product_name or "").strip().lower()
		consumed[key] = consumed.get(key, 0) + (e.qty_out or 0)
	return consumed

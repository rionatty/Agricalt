# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""TFOP Actual — an actual-spend posting against a specific TFOP budget line.

`against` is a Dynamic Link whose target doctype is derived from cost_category:
    Products / Marketing Material -> Item
    Activities                    -> Marketing Activity Type
    Other Cost                    -> Budget Category
On submit/cancel the parent TFOP re-rolls cumulative actuals per line.
"""
import frappe
from frappe.model.document import Document

_AGAINST_TYPE = {
	"Products": "Item",
	"Marketing Material": "Item",
	"Activities": "Marketing Activity Type",
	"Other Cost": "Budget Category",
}


class TFOPActual(Document):
	def validate(self):
		# Drive the Dynamic Link target doctype from the chosen cost category.
		self.against_type = _AGAINST_TYPE.get(self.cost_category)
		if not self.against_type:
			self.against = None

	def on_submit(self):
		self._update_parent()

	def on_cancel(self):
		self._update_parent()

	def _update_parent(self):
		if self.tfop and frappe.db.exists("TFOP", self.tfop):
			frappe.get_doc("TFOP", self.tfop).recalc_actuals()

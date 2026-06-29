# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""TFOP Actual — an actual-spend document posted against a TFOP campaign.

Mirrors the TFOP layout: selecting a campaign loads its budget lines into the
four actual tables (client script), the user enters the actual against each line,
and on submit the parent TFOP re-rolls cumulative actuals per line.
"""
import frappe
from frappe.model.document import Document
from frappe.utils import flt

_ACTUAL_TABLES = ("product_actuals", "activity_actuals", "material_actuals", "other_actuals")


class TFOPActual(Document):
	def validate(self):
		self.total_actual = sum(
			flt(row.actual_amount)
			for table in _ACTUAL_TABLES
			for row in self.get(table)
		)

	def on_submit(self):
		self._update_parent()

	def on_cancel(self):
		self._update_parent()

	def _update_parent(self):
		if self.tfop and frappe.db.exists("TFOP", self.tfop):
			frappe.get_doc("TFOP", self.tfop).recalc_actuals()

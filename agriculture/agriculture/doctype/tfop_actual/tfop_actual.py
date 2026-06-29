# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""TFOP Actual — an actual-spend posting against a TFOP campaign budget.

Submitting / cancelling one of these re-rolls the parent TFOP's actual total so
the budget-vs-actual variance stays live.
"""
import frappe
from frappe.model.document import Document


class TFOPActual(Document):
	def on_submit(self):
		self._update_parent()

	def on_cancel(self):
		self._update_parent()

	def _update_parent(self):
		if self.tfop and frappe.db.exists("TFOP", self.tfop):
			frappe.get_doc("TFOP", self.tfop).recalc_actuals()

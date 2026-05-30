# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AgricultureSettings(Document):
	pass


def get_settings():
	"""Convenience accessor for the single Agriculture Settings doc (cached)."""
	return frappe.get_cached_doc("Agriculture Settings")


def get_int(fieldname, default=0):
	val = frappe.db.get_single_value("Agriculture Settings", fieldname)
	return int(val) if val else default

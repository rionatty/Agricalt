# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt
"""
Farmer Visit History — supports the §11 historical query:
"identify if the same customer was visited the previous week by a different promoter".
Flags farmers visited by more than one promoter in the period.
"""

import frappe
from frappe import _


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "activity_date", "fieldtype": "Date", "width": 100},
		{"label": _("Farmer"), "fieldname": "farmer", "fieldtype": "Link", "options": "Farmer", "width": 120},
		{"label": _("Farmer Name"), "fieldname": "farmer_name", "fieldtype": "Data", "width": 160},
		{"label": _("Promoter"), "fieldname": "promoter_name", "fieldtype": "Data", "width": 150},
		{"label": _("Activity"), "fieldname": "activity_type", "fieldtype": "Data", "width": 120},
		{"label": _("Location"), "fieldname": "location_name", "fieldtype": "Data", "width": 130},
		{"label": _("Activity Log"), "fieldname": "name", "fieldtype": "Link", "options": "Field Activity Log", "width": 130},
		{"label": _("Multi-Promoter?"), "fieldname": "multi_flag", "fieldtype": "Data", "width": 140},
	]


def get_data(filters):
	conditions = {"farmer": ["is", "set"]}
	if filters.get("farmer"):
		conditions["farmer"] = filters["farmer"]
	if filters.get("promoter"):
		conditions["promoter"] = filters["promoter"]
	if filters.get("from_date") and filters.get("to_date"):
		conditions["activity_date"] = ["between", [filters["from_date"], filters["to_date"]]]

	logs = frappe.get_all("Field Activity Log", filters=conditions, fields=[
		"name", "activity_date", "farmer", "farmer_name", "promoter", "promoter_name",
		"activity_type", "location_name",
	], order_by="farmer asc, activity_date asc")

	# Determine which farmers were visited by >1 distinct promoter
	farmer_promoters = {}
	for log in logs:
		farmer_promoters.setdefault(log.farmer, set()).add(log.promoter)

	for log in logs:
		distinct = farmer_promoters.get(log.farmer, set())
		log["multi_flag"] = "⚠ Yes" if len(distinct) > 1 else ""

	return logs

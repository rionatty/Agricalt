# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import date_diff, today


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Demo Garden"), "fieldname": "name", "fieldtype": "Link", "options": "Demo Garden", "width": 110},
		{"label": _("Name"), "fieldname": "demo_garden_name", "fieldtype": "Data", "width": 180},
		{"label": _("Promoter"), "fieldname": "responsible_promoter_name", "fieldtype": "Data", "width": 150},
		{"label": _("Location"), "fieldname": "location", "fieldtype": "Data", "width": 130},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": _("Planting Date"), "fieldname": "planting_date", "fieldtype": "Date", "width": 110},
		{"label": _("Exp. Harvest"), "fieldname": "expected_harvest_date", "fieldtype": "Date", "width": 110},
		{"label": _("Days to Harvest"), "fieldname": "days_to_harvest", "fieldtype": "Int", "width": 120},
		{"label": _("Flag"), "fieldname": "flag", "fieldtype": "Data", "width": 220},
	]


def get_data(filters):
	conditions = {}
	if filters.get("status"):
		conditions["status"] = filters["status"]
	if filters.get("promoter"):
		conditions["responsible_promoter"] = filters["promoter"]

	gardens = frappe.get_all("Demo Garden", filters=conditions, fields=[
		"name", "demo_garden_name", "responsible_promoter", "responsible_promoter_name",
		"location", "status", "planting_date", "expected_harvest_date",
	], order_by="expected_harvest_date asc")

	rows = []
	for g in gardens:
		days = date_diff(g.expected_harvest_date, today()) if g.expected_harvest_date else None

		flag = ""
		# Materials received but not planted
		if g.status == "Material Received" and not g.planting_date:
			has_receipt = frappe.db.exists("Demo Garden Material Request",
			                               {"demo_garden": g.name, "status": "Received"})
			if has_receipt:
				flag = "⚠ Materials received, not planted"
		# Approaching / overdue harvest
		elif days is not None and g.status not in ("Field Day Done", "Completed"):
			if days < 0:
				flag = "🔴 Field day overdue"
			elif days <= 7:
				flag = "🟠 Harvest approaching"
		# Planted but no inputs
		if g.status in ("Planted", "Monitoring"):
			has_input = frappe.db.exists("Demo Garden Input Application",
			                             {"demo_garden": g.name, "status": "Submitted"})
			if not has_input and not flag:
				flag = "⚠ Planted, no inputs applied"

		g["days_to_harvest"] = days
		g["flag"] = flag
		rows.append(g)

	return rows

# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Promoter"), "fieldname": "promoter_name", "fieldtype": "Data", "width": 160},
		{"label": _("Product / Material"), "fieldname": "product_name", "fieldtype": "Data", "width": 180},
		{"label": _("Unit"), "fieldname": "uom", "fieldtype": "Data", "width": 70},
		{"label": _("Received"), "fieldname": "received", "fieldtype": "Float", "width": 100},
		{"label": _("Consumed"), "fieldname": "consumed", "fieldtype": "Float", "width": 100},
		{"label": _("Balance"), "fieldname": "balance", "fieldtype": "Float", "width": 100},
		{"label": _("Status"), "fieldname": "flag", "fieldtype": "Data", "width": 160},
	]


def get_data(filters):
	conditions = {}
	if filters.get("promoter"):
		conditions["promoter"] = filters["promoter"]
	if filters.get("from_date") and filters.get("to_date"):
		conditions["transaction_date"] = ["between", [filters["from_date"], filters["to_date"]]]

	entries = frappe.get_all("Promoter Stock Ledger", filters=conditions, fields=[
		"promoter", "promoter_name", "product_name", "uom", "qty_in", "qty_out",
	])

	# Aggregate per promoter + product
	agg = {}
	for e in entries:
		key = (e.promoter, e.product_name)
		if key not in agg:
			agg[key] = {"promoter_name": e.promoter_name, "product_name": e.product_name,
			            "uom": e.uom, "received": 0.0, "consumed": 0.0}
		agg[key]["received"] += flt(e.qty_in)
		agg[key]["consumed"] += flt(e.qty_out)

	rows = []
	for v in agg.values():
		v["balance"] = v["received"] - v["consumed"]
		if v["balance"] > 0.001 and v["consumed"] == 0:
			v["flag"] = "⚠ Received, none used"
		elif v["balance"] > 0.001:
			v["flag"] = "🟠 Partially used"
		else:
			v["flag"] = "✔ Fully utilised"
		rows.append(v)

	rows.sort(key=lambda r: (r["promoter_name"] or "", r["product_name"] or ""))
	return rows

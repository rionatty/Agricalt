# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from agriculture.agriculture.doctype.promoter_kpi_target.promoter_kpi_target import get_targets_for


def execute(filters=None):
	filters = filters or {}
	columns = get_columns()
	data = get_data(filters)
	return columns, data


def get_columns():
	return [
		{"label": _("Promoter"), "fieldname": "promoter", "fieldtype": "Link", "options": "Field Promoter", "width": 130},
		{"label": _("Name"), "fieldname": "promoter_name", "fieldtype": "Data", "width": 160},
		{"label": _("Region"), "fieldname": "region", "fieldtype": "Data", "width": 100},
		{"label": _("Farm Visits"), "fieldname": "farm_visits", "fieldtype": "Int", "width": 100},
		{"label": _("Demo Gardens"), "fieldname": "demo_gardens", "fieldtype": "Int", "width": 110},
		{"label": _("Trainings"), "fieldname": "trainings", "fieldtype": "Int", "width": 90},
		{"label": _("Exhibitions"), "fieldname": "exhibitions", "fieldtype": "Int", "width": 95},
		{"label": _("Stockist Visits"), "fieldname": "stockist_visits", "fieldtype": "Int", "width": 110},
		{"label": _("Orders (UGX)"), "fieldname": "orders_value", "fieldtype": "Currency", "width": 130},
		{"label": _("Target Visits"), "fieldname": "target_farm_visits", "fieldtype": "Int", "width": 100},
		{"label": _("% of Target"), "fieldname": "pct_target", "fieldtype": "Percent", "width": 100},
		{"label": _("KPI Met?"), "fieldname": "kpi_met", "fieldtype": "Data", "width": 90},
	]


def get_data(filters):
	conditions = {}
	if filters.get("promoter"):
		conditions["name"] = filters["promoter"]
	if filters.get("region"):
		conditions["region"] = filters["region"]
	conditions["status"] = "Active"

	promoters = frappe.get_all("Field Promoter", filters=conditions,
	                           fields=["name", "promoter_name", "region"])

	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	date_filter = {}
	if from_date and to_date:
		date_filter = {"activity_date": ["between", [from_date, to_date]]}

	rows = []
	for p in promoters:
		af = dict(date_filter, promoter=p.name)

		def count(activity):
			return frappe.db.count("Field Activity Log", dict(af, activity_type=activity))

		farm_visits = count("Farm Visit")
		stockist_visits = count("Stockist Visit")
		exhibitions = count("Exhibition")
		trainings = count("Farmer Training")

		# Demo gardens registered in window
		dg_filter = {"responsible_promoter": p.name}
		if from_date and to_date:
			dg_filter["creation"] = ["between", [from_date, to_date + " 23:59:59"]]
		demo_gardens = frappe.db.count("Demo Garden", dg_filter)

		# Orders value
		oc_filter = {"promoter": p.name, "status": ["in", ["Submitted", "Processed in ERP"]]}
		if from_date and to_date:
			oc_filter["collection_date"] = ["between", [from_date, to_date]]
		orders = frappe.get_all("Order Collection", filters=oc_filter, fields=["total_order_value"])
		orders_value = sum(flt(o.total_order_value) for o in orders)

		targets = get_targets_for(p.name, to_date)
		tgt_visits = targets.get("target_farm_visits") or 0
		pct = (farm_visits / tgt_visits * 100) if tgt_visits else 0

		rows.append({
			"promoter": p.name,
			"promoter_name": p.promoter_name,
			"region": p.region,
			"farm_visits": farm_visits,
			"demo_gardens": demo_gardens,
			"trainings": trainings,
			"exhibitions": exhibitions,
			"stockist_visits": stockist_visits,
			"orders_value": orders_value,
			"target_farm_visits": tgt_visits,
			"pct_target": pct,
			"kpi_met": "✔ Yes" if tgt_visits and farm_visits >= tgt_visits else ("✗ No" if tgt_visits else "—"),
		})

	rows.sort(key=lambda r: r["pct_target"], reverse=True)
	return rows

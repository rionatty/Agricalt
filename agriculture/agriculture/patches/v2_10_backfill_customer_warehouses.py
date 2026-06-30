# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Re-backfill customer warehouses.

The first backfill (v2_8) failed for every customer because the warehouse was
created with warehouse_type="Stores", which doesn't exist on sites without that
Warehouse Type. The hook now omits the type when it's missing, so re-run the
backfill — every customer without a crm_warehouse gets one.
"""
import frappe


def execute():
	from agriculture.agriculture.customer_hooks import ensure_customer_warehouse
	for name in frappe.get_all("Customer", filters={"crm_warehouse": ["in", ["", None]]}, pluck="name"):
		try:
			ensure_customer_warehouse(frappe.get_doc("Customer", name))
		except Exception as e:
			frappe.log_error(f"Backfill warehouse for {name}: {e}", "Customer Warehouse Backfill v2_10")
	frappe.db.commit()

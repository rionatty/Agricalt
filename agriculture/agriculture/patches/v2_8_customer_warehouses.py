# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Channel stock visibility — every Customer is modelled as a Warehouse.

1. Ensure the channel Customer Groups (Distributor, Stockist, Farmer) exist.
2. Make the crm_warehouse field apply to all customers (drop the is_distributor
   depends_on left over from the distributor-only model).
3. Backfill a warehouse for every existing customer that lacks one.
"""
import frappe

CHANNEL_GROUPS = ["Distributor", "Stockist", "Farmer"]


def execute():
	# 1. Channel Customer Groups.
	parent_group = frappe.db.get_value("Customer Group", {"is_group": 1}, "name") or "All Customer Groups"
	for g in CHANNEL_GROUPS:
		if not frappe.db.exists("Customer Group", g):
			frappe.get_doc({
				"doctype": "Customer Group",
				"customer_group_name": g,
				"parent_customer_group": parent_group,
				"is_group": 0,
			}).insert(ignore_permissions=True)

	# 2. crm_warehouse now applies to every customer.
	cf = frappe.db.get_value("Custom Field", {"dt": "Customer", "fieldname": "crm_warehouse"}, "name")
	if cf:
		frappe.db.set_value("Custom Field", cf, {
			"depends_on": "",
			"description": "Auto-created per customer (under a warehouse group for the Customer Group). "
			               "Holds this customer's stock for channel movement tracking.",
		})

	# 3. Backfill a warehouse for every existing customer that lacks one.
	from agriculture.agriculture.customer_hooks import ensure_customer_warehouse
	for name in frappe.get_all("Customer", filters={"crm_warehouse": ["in", ["", None]]}, pluck="name"):
		try:
			ensure_customer_warehouse(frappe.get_doc("Customer", name))
		except Exception as e:
			frappe.log_error(f"Backfill warehouse for {name}: {e}", "Customer Warehouse Backfill")

	frappe.db.commit()

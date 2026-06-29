"""Add warehouse-to-SAP mapping fields.

1. sap_warehouse_code on Warehouse — admin fills once per warehouse.
2. default_warehouse on User — admin sets once per user.

All SAP push functions resolve the SAP code from the Warehouse record automatically.
"""
import frappe


def execute():
	# 1. SAP code on each Warehouse record
	if not frappe.db.exists("Custom Field", {"dt": "Warehouse", "fieldname": "sap_warehouse_code"}):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "Warehouse",
			"fieldname": "sap_warehouse_code",
			"label": "SAP B1 Warehouse Code",
			"fieldtype": "Data",
			"insert_after": "warehouse_name",
			"description": (
				"SAP B1 warehouse code (e.g. FG, STORE-01). "
				"Set once — resolved automatically on all SAP transfers."
			),
		}).insert(ignore_permissions=True)

	# 2. Default warehouse on each User record
	if not frappe.db.exists("Custom Field", {"dt": "User", "fieldname": "default_warehouse"}):
		frappe.get_doc({
			"doctype": "Custom Field",
			"dt": "User",
			"fieldname": "default_warehouse",
			"label": "Default Warehouse",
			"fieldtype": "Link",
			"options": "Warehouse",
			"insert_after": "user_image",
			"description": "The warehouse this user works from. Auto-fills the From Warehouse on material requests.",
		}).insert(ignore_permissions=True)

	frappe.db.commit()

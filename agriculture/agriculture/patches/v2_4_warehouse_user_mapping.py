"""Add sap_warehouse_code custom field to Warehouse doctype.

Admins set this once per warehouse so all SAP push functions can resolve
the correct SAP B1 WarehouseCode automatically — no manual entry by users.
"""
import frappe


def execute():
	if frappe.db.exists("Custom Field", {"dt": "Warehouse", "fieldname": "sap_warehouse_code"}):
		return

	frappe.get_doc({
		"doctype": "Custom Field",
		"dt": "Warehouse",
		"fieldname": "sap_warehouse_code",
		"label": "SAP B1 Warehouse Code",
		"fieldtype": "Data",
		"insert_after": "warehouse_name",
		"description": (
			"SAP B1 warehouse code used when pushing documents to SAP B1 "
			"(e.g. FG, STORE-01, EVENT-WH). Set once — resolved automatically on all transfers."
		),
	}).insert(ignore_permissions=True)
	frappe.db.commit()

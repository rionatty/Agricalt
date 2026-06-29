# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Add sap_supplier_code to the User doctype.

Each user is mapped to a default SAP vendor/supplier CardCode, which auto-fills
the 'Pay To' on a Cash Requisition (editable per requisition).
"""
import frappe


def execute():
	if frappe.db.exists("Custom Field", {"dt": "User", "fieldname": "sap_supplier_code"}):
		return

	frappe.get_doc({
		"doctype": "Custom Field",
		"dt": "User",
		"fieldname": "sap_supplier_code",
		"label": "SAP Supplier Code",
		"fieldtype": "Data",
		"insert_after": "default_warehouse",
		"description": (
			"SAP B1 vendor/supplier CardCode used as the default 'Pay To' on this "
			"user's Cash Requisitions (A/P Down Payment Requests). Editable per requisition."
		),
	}).insert(ignore_permissions=True)
	frappe.db.commit()

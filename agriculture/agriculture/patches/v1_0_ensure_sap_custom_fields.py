# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt
"""
Patch: create sap_card_code (Customer) and sap_synced (Item) custom fields.

These fields are required for SAP B1 master-data sync. Sites that had the app
installed before ensure_custom_fields() was added will be missing the columns,
causing OperationalError 1054 on pull_customers / pull_items.
Running this patch via bench migrate creates the columns if absent.
"""

import frappe


def execute():
	from agriculture.agriculture.setup import ensure_custom_fields
	ensure_custom_fields()
	frappe.db.commit()

# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Distributor = Warehouse model (Twiga CRM — Masters).

When a Customer is flagged as a Distributor, auto-create (once) a CRM Warehouse
that holds the SAP-delivered stock baseline. This mirrors the Field Promoter
warehouse pattern in field_promoter.py. Non-fatal: a warehouse failure must
never block saving the Customer.
"""
import frappe


def ensure_distributor_warehouse(doc, method=None):
	"""doc_event on Customer (on_update). Idempotent — runs on every save but
	only creates the warehouse once, then links it via `crm_warehouse`."""
	if not doc.get("is_distributor"):
		return
	if doc.get("crm_warehouse"):
		return

	warehouse_name = f"{doc.customer_name} - Distributor Store"
	existing = frappe.db.get_value("Warehouse", {"warehouse_name": warehouse_name}, "name")
	if existing:
		frappe.db.set_value("Customer", doc.name, "crm_warehouse", existing)
		return

	try:
		company = (
			frappe.db.get_single_value("Global Defaults", "default_company")
			or frappe.db.get_value("Company", {}, "name")
			or ""
		)
		parent_warehouse = frappe.db.get_value(
			"Warehouse", {"is_group": 1, "company": company}, "name"
		) or "All Warehouses"

		wh = frappe.get_doc({
			"doctype": "Warehouse",
			"warehouse_name": warehouse_name,
			"parent_warehouse": parent_warehouse,
			"company": company,
			"warehouse_type": "Stores",
			"is_group": 0,
		})
		wh.flags.ignore_permissions = True
		wh.insert()
		frappe.db.set_value("Customer", doc.name, "crm_warehouse", wh.name)
		frappe.db.commit()
	except Exception as e:
		# Non-fatal — Customer save must not be blocked by warehouse creation.
		frappe.log_error(
			f"Could not create distributor warehouse for {doc.name}: {e}",
			"Distributor Warehouse Creation",
		)

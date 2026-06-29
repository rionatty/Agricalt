# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Customer = Warehouse model (Twiga CRM — channel stock visibility).

Every Customer (Distributor, Stockist, Farmer, or any other Customer Group) is
modelled as its own Warehouse so we can trace stock holding per customer. The
warehouses are organised under a group-warehouse per Customer Group, so stock
rolls up by channel type in the Warehouse tree / Stock Balance report.

Non-fatal: a warehouse failure must never block saving the Customer.
"""
import frappe


def _default_company():
	return (
		frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
		or ""
	)


def _company_root_warehouse(company):
	"""The top group warehouse for a company (parentless is_group)."""
	return (
		frappe.db.get_value(
			"Warehouse",
			{"company": company, "is_group": 1, "parent_warehouse": ["in", [None, ""]]},
			"name",
		)
		or frappe.db.get_value("Warehouse", {"company": company, "is_group": 1}, "name")
		or "All Warehouses"
	)


def _ensure_group_warehouse(group_label, company):
	"""Ensure a group (is_group=1) warehouse exists for a Customer Group, under the
	company root, and return its name. Idempotent."""
	existing = frappe.db.get_value(
		"Warehouse", {"warehouse_name": group_label, "company": company, "is_group": 1}, "name"
	)
	if existing:
		return existing
	g = frappe.get_doc({
		"doctype": "Warehouse",
		"warehouse_name": group_label,
		"company": company,
		"is_group": 1,
		"parent_warehouse": _company_root_warehouse(company),
	})
	g.flags.ignore_permissions = True
	g.insert()
	return g.name


def ensure_customer_warehouse(doc, method=None):
	"""doc_event on Customer (on_update). Idempotent — creates a per-customer
	warehouse once (under the customer's group warehouse), then links it via
	`crm_warehouse`."""
	if doc.get("crm_warehouse"):
		return
	if doc.get("disabled"):
		return

	try:
		company = _default_company()
		if not company:
			return

		group_label = doc.get("customer_group") or "Customers"
		parent = _ensure_group_warehouse(group_label, company)

		# ERPNext appends " - {company abbr}" to the warehouse name on insert.
		existing = frappe.db.get_value(
			"Warehouse",
			{"warehouse_name": doc.customer_name, "company": company, "is_group": 0},
			"name",
		)
		if existing:
			frappe.db.set_value("Customer", doc.name, "crm_warehouse", existing)
			return

		wh = frappe.get_doc({
			"doctype": "Warehouse",
			"warehouse_name": doc.customer_name,
			"parent_warehouse": parent,
			"company": company,
			"warehouse_type": "Stores",
			"is_group": 0,
		})
		wh.flags.ignore_permissions = True
		wh.insert()
		frappe.db.set_value("Customer", doc.name, "crm_warehouse", wh.name)
		frappe.db.commit()
	except Exception as e:
		# Non-fatal — saving the Customer must not be blocked by warehouse creation.
		frappe.log_error(
			f"Could not create customer warehouse for {doc.name}: {e}",
			"Customer Warehouse Creation",
		)


# Backwards-compatible alias (older hooks referenced this name).
ensure_distributor_warehouse = ensure_customer_warehouse

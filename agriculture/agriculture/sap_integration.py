# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt
"""
SAP Business One integration layer.

SAP B1 remains the ERP system of record. Orders and payments collected in the
field (ERPNext) are pushed to SAP B1 via the Service Layer REST API.

This module provides the full plumbing — authentication, push, sync logging,
and the auto-push hook. The only thing to finalise once Syova's IT confirms the
SAP B1 API spec is the exact JSON field mapping inside `_build_order_payload`
(SAP B1 Service Layer expects standard `Orders` object fields — CardCode,
DocDueDate, DocumentLines[].ItemCode/Quantity/UnitPrice).
"""

import json

import frappe
from frappe import _
from frappe.utils import getdate


# ─── Hook entry point ────────────────────────────────────────────────────────
def on_order_update(doc, method=None):
	"""Auto-push an Order Collection to SAP B1 when submitted, if enabled."""
	settings = frappe.get_cached_doc("Agriculture Settings")
	if not settings.sap_b1_enabled or not settings.sap_auto_push_orders:
		return
	if doc.status != "Submitted" or doc.erp_synced:
		return
	# Push in background so the user isn't blocked on SAP latency
	frappe.enqueue(
		"agriculture.agriculture.sap_integration.push_order",
		queue="long",
		order_name=doc.name,
	)


# ─── Public API ──────────────────────────────────────────────────────────────
@frappe.whitelist()
def push_order(order_name):
	"""Push a single Order Collection to SAP B1. Returns the sync log name."""
	order = frappe.get_doc("Order Collection", order_name)
	settings = frappe.get_cached_doc("Agriculture Settings")

	log = frappe.new_doc("SAP B1 Sync Log")
	log.reference_doctype = "Order Collection"
	log.reference_name = order.name
	log.sync_type = "Order"
	log.status = "Pending"

	if not settings.sap_b1_enabled:
		log.status = "Failed"
		log.error_message = "SAP B1 integration is disabled in Agriculture Settings."
		log.insert(ignore_permissions=True)
		return log.name

	try:
		payload = _build_order_payload(order, settings)
		log.request_payload = json.dumps(payload, indent=2)

		response = _post_to_sap(settings, "Orders", payload)
		log.response_text = json.dumps(response, indent=2)[:140000]
		log.status = "Success"
		log.sap_document_number = str(response.get("DocNum") or response.get("DocEntry") or "")

		# Mark the order as synced
		frappe.db.set_value("Order Collection", order.name, {
			"erp_synced": 1,
			"erp_sales_order": log.sap_document_number,
			"status": "Processed in ERP",
		})
	except Exception as e:
		log.status = "Failed"
		log.error_message = str(e)[:1000]
		frappe.log_error(frappe.get_traceback(), "SAP B1 Order Push Failed")

	log.insert(ignore_permissions=True)
	frappe.db.commit()
	return log.name


# ─── SAP B1 Service Layer plumbing ───────────────────────────────────────────
def _get_session(settings):
	"""Authenticate against the SAP B1 Service Layer and return (base_url, cookies)."""
	import requests  # imported lazily so the app loads even if requests is absent

	base = (settings.sap_b1_base_url or "").rstrip("/")
	if not base:
		frappe.throw(_("SAP B1 Service Layer URL is not configured."))

	resp = requests.post(
		f"{base}/Login",
		json={
			"CompanyDB": settings.sap_b1_company_db,
			"UserName": settings.sap_b1_username,
			"Password": settings.get_password("sap_b1_password"),
		},
		verify=False,
		timeout=30,
	)
	resp.raise_for_status()
	return base, resp.cookies


def _post_to_sap(settings, endpoint, payload):
	import requests

	base, cookies = _get_session(settings)
	resp = requests.post(
		f"{base}/{endpoint}",
		json=payload,
		cookies=cookies,
		verify=False,
		timeout=60,
	)
	if resp.status_code not in (200, 201):
		raise Exception(f"SAP B1 returned {resp.status_code}: {resp.text[:500]}")
	return resp.json()


def _build_order_payload(order, settings):
	"""
	Map an ERPNext Order Collection to the SAP B1 Service Layer `Orders` object.

	NOTE: CardCode mapping assumes the ERP Customer's name equals the SAP B1
	BusinessPartner CardCode. Confirm with Syova IT during the integration phase.
	"""
	card_code = order.stockist or ""
	lines = []
	for item in order.items:
		lines.append({
			"ItemCode": item.item or item.product_name,
			"Quantity": item.quantity or 0,
			"UnitPrice": item.unit_price or 0,
			"WarehouseCode": settings.sap_default_warehouse or "",
		})

	return {
		"CardCode": card_code,
		"DocDueDate": str(getdate(order.collection_date)),
		"Comments": f"Field order via CyveTech — {order.name} (Promoter: {order.promoter_name or order.promoter})",
		"U_CyveTechRef": order.name,  # UDF to trace back to the field record
		"DocumentLines": lines,
	}


@frappe.whitelist()
def test_connection():
	"""Admin helper — verifies SAP B1 credentials from Settings."""
	settings = frappe.get_cached_doc("Agriculture Settings")
	try:
		_get_session(settings)
		return {"ok": True, "message": _("Successfully connected to SAP B1.")}
	except Exception as e:
		return {"ok": False, "message": str(e)}

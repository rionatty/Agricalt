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
from frappe.utils import getdate, flt, today as _frappe_today


# ─── Hook entry points ───────────────────────────────────────────────────────
def on_order_update(doc, method=None):
	"""Auto-push an Order Collection to SAP B1 when submitted, if enabled."""
	settings = frappe.get_cached_doc("Agriculture Settings")
	if not settings.sap_b1_enabled or doc.status != "Submitted":
		return

	if settings.sap_auto_push_orders and not doc.erp_synced:
		frappe.enqueue(
			"agriculture.agriculture.sap_integration.push_order",
			queue="long",
			order_name=doc.name,
		)

	if settings.sap_auto_push_payments and doc.payment_collected and doc.payment_amount:
		already_pushed = frappe.db.exists("SAP B1 Sync Log", {
			"reference_doctype": "Order Collection",
			"reference_name": doc.name,
			"sync_type": "Payment",
			"status": "Success",
		})
		if not already_pushed:
			frappe.enqueue(
				"agriculture.agriculture.sap_integration.push_payment",
				queue="long",
				order_name=doc.name,
			)


def on_material_request_update(doc, method=None):
	"""
	Push Demo Garden Material Request to SAP B1:
	- On Submitted → create a SAP B1 Stock Transfer Request (from main warehouse to promoter)
	- On Issued    → create a SAP B1 Stock Transfer (actual movement)
	- On Received  → create a SAP B1 Goods Receipt to confirm promoter received stock
	"""
	settings = frappe.get_cached_doc("Agriculture Settings")
	if not settings.sap_b1_enabled:
		return

	if doc.status == "Submitted":
		# Push as a Stock Transfer Request so store team sees it in SAP
		already_pushed = frappe.db.exists("SAP B1 Sync Log", {
			"reference_doctype": "Demo Garden Material Request",
			"reference_name": doc.name,
			"sync_type": "StockTransferRequest",
			"status": "Success",
		})
		if not already_pushed:
			frappe.enqueue(
				"agriculture.agriculture.sap_integration.push_stock_transfer_request",
				queue="long",
				request_name=doc.name,
			)

	elif doc.status == "Issued":
		# Push actual stock transfer (store → promoter warehouse)
		already_pushed = frappe.db.exists("SAP B1 Sync Log", {
			"reference_doctype": "Demo Garden Material Request",
			"reference_name": doc.name,
			"sync_type": "Inventory",
			"status": "Success",
		})
		if not already_pushed:
			frappe.enqueue(
				"agriculture.agriculture.sap_integration.push_material_issuance",
				queue="long",
				request_name=doc.name,
			)

	elif doc.status == "Received":
		# Confirm receipt in SAP B1
		already_pushed = frappe.db.exists("SAP B1 Sync Log", {
			"reference_doctype": "Demo Garden Material Request",
			"reference_name": doc.name,
			"sync_type": "GoodsReceipt",
			"status": "Success",
		})
		if not already_pushed:
			frappe.enqueue(
				"agriculture.agriculture.sap_integration.push_stock_receipt",
				queue="long",
				request_name=doc.name,
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


@frappe.whitelist()
def push_payment(order_name):
	"""Push a payment collected on an Order Collection to SAP B1 IncomingPayments."""
	order = frappe.get_doc("Order Collection", order_name)
	settings = frappe.get_cached_doc("Agriculture Settings")

	log = frappe.new_doc("SAP B1 Sync Log")
	log.reference_doctype = "Order Collection"
	log.reference_name = order.name
	log.sync_type = "Payment"
	log.status = "Pending"

	if not settings.sap_b1_enabled:
		log.status = "Failed"
		log.error_message = "SAP B1 integration is disabled in Agriculture Settings."
		log.insert(ignore_permissions=True)
		return log.name

	try:
		payload = _build_payment_payload(order, settings)
		log.request_payload = json.dumps(payload, indent=2)

		response = _post_to_sap(settings, "IncomingPayments", payload)
		log.response_text = json.dumps(response, indent=2)[:140000]
		log.status = "Success"
		log.sap_document_number = str(response.get("DocNum") or response.get("DocEntry") or "")
	except Exception as e:
		log.status = "Failed"
		log.error_message = str(e)[:1000]
		frappe.log_error(frappe.get_traceback(), "SAP B1 Payment Push Failed")

	log.insert(ignore_permissions=True)
	frappe.db.commit()
	return log.name


@frappe.whitelist()
def push_material_issuance(request_name):
	"""Push a Demo Garden Material Request (status=Issued) as a SAP B1 Goods Issue."""
	from frappe.utils import today as _today
	request = frappe.get_doc("Demo Garden Material Request", request_name)
	settings = frappe.get_cached_doc("Agriculture Settings")

	log = frappe.new_doc("SAP B1 Sync Log")
	log.reference_doctype = "Demo Garden Material Request"
	log.reference_name = request.name
	log.sync_type = "Inventory"
	log.status = "Pending"

	if not settings.sap_b1_enabled:
		log.status = "Failed"
		log.error_message = "SAP B1 integration is disabled in Agriculture Settings."
		log.insert(ignore_permissions=True)
		return log.name

	try:
		payload = _build_goods_issue_payload(request, settings, _today)
		log.request_payload = json.dumps(payload, indent=2)

		response = _post_to_sap(settings, "InventoryGenExits", payload)
		log.response_text = json.dumps(response, indent=2)[:140000]
		log.status = "Success"
		log.sap_document_number = str(response.get("DocNum") or response.get("DocEntry") or "")
	except Exception as e:
		log.status = "Failed"
		log.error_message = str(e)[:1000]
		frappe.log_error(frappe.get_traceback(), "SAP B1 Inventory Push Failed")

	log.insert(ignore_permissions=True)
	frappe.db.commit()
	return log.name


@frappe.whitelist()
def push_stock_transfer_request(request_name):
	"""Push a Demo Garden Material Request (status=Submitted) to SAP B1 as a Stock Transfer Request."""
	from frappe.utils import today as _today
	request = frappe.get_doc("Demo Garden Material Request", request_name)
	settings = frappe.get_cached_doc("Agriculture Settings")

	log = frappe.new_doc("SAP B1 Sync Log")
	log.reference_doctype = "Demo Garden Material Request"
	log.reference_name = request.name
	log.sync_type = "StockTransferRequest"
	log.status = "Pending"

	try:
		# Get the promoter's warehouse (stored as an ERPNext Warehouse or raw SAP code)
		promoter_wh_raw = frappe.db.get_value(
			"Field Promoter", request.promoter, "promoter_warehouse"
		)
		from_sap = _resolve_sap_warehouse(None, settings.sap_default_warehouse)
		to_sap = _resolve_sap_warehouse(promoter_wh_raw, settings.sap_default_warehouse)
		_assert_distinct_sap_warehouses(
			from_sap, to_sap,
			ctx=f"promoter_warehouse={promoter_wh_raw}",
		)

		# SAP B1 StockTransferLine: WarehouseCode = destination, FromWarehouseCode = source.
		lines = []
		for item in request.items:
			lines.append({
				"ItemCode": item.item or item.item_name,
				"Quantity": float(item.quantity_requested or 0),
				"FromWarehouseCode": from_sap,
				"WarehouseCode": to_sap,
			})

		payload = {
			"DocDate": str(getdate(request.request_date or _today())),
			"Comments": f"Demo material request — {request.name} for {request.demo_garden} (Promoter: {request.promoter})",
			"FromWarehouse": from_sap,
			"ToWarehouse": to_sap,
			"StockTransferLines": lines,
		}
		log.request_payload = json.dumps(payload, indent=2)
		response = _post_to_sap(settings, "InventoryTransferRequests", payload)
		log.response_text = json.dumps(response, indent=2)[:140000]
		log.status = "Success"
		log.sap_document_number = str(response.get("DocNum") or response.get("DocEntry") or "")

		# Store SAP transfer request number back on the material request
		frappe.db.set_value("Demo Garden Material Request", request.name,
			"sap_transfer_request_number", log.sap_document_number)
	except Exception as e:
		log.status = "Failed"
		log.error_message = str(e)[:1000]
		frappe.log_error(frappe.get_traceback(), "SAP B1 Stock Transfer Request Failed")

	log.insert(ignore_permissions=True)
	frappe.db.commit()
	return log.name


@frappe.whitelist()
def push_marketing_material_request(request_name):
	"""Push a submitted Marketing Material Request to SAP B1 as a Stock Transfer
	Request (from_warehouse -> to_warehouse)."""
	from frappe.utils import today as _today
	request = frappe.get_doc("Marketing Material Request", request_name)
	settings = frappe.get_cached_doc("Agriculture Settings")

	log = frappe.new_doc("SAP B1 Sync Log")
	log.reference_doctype = "Marketing Material Request"
	log.reference_name = request.name
	log.sync_type = "StockTransferRequest"
	log.status = "Pending"

	try:
		from_sap = _resolve_sap_warehouse(request.from_warehouse, settings.sap_default_warehouse)
		to_sap = _resolve_sap_warehouse(request.to_warehouse, settings.sap_default_warehouse)
		_assert_distinct_sap_warehouses(
			from_sap, to_sap,
			ctx=f"from={request.from_warehouse}, to={request.to_warehouse}",
		)

		# SAP B1 StockTransferLine: WarehouseCode = destination, FromWarehouseCode = source.
		lines = []
		for item in request.items:
			lines.append({
				"ItemCode": item.item or item.item_name,
				"Quantity": float(item.qty or 0),
				"FromWarehouseCode": from_sap,
				"WarehouseCode": to_sap,
			})

		comment = f"Marketing material request — {request.name}"
		if request.tfop:
			comment += f" for TFOP {request.tfop}"
		payload = {
			"DocDate": str(getdate(request.request_date or _today())),
			"Comments": comment,
			"FromWarehouse": from_sap,
			"ToWarehouse": to_sap,
			"StockTransferLines": lines,
		}
		log.request_payload = json.dumps(payload, indent=2)
		response = _post_to_sap(settings, "InventoryTransferRequests", payload)
		log.response_text = json.dumps(response, indent=2)[:140000]
		log.status = "Success"
		log.sap_document_number = str(response.get("DocNum") or response.get("DocEntry") or "")

		frappe.db.set_value("Marketing Material Request", request.name, {
			"sap_transfer_request_number": log.sap_document_number,
			"sap_transfer_docentry": str(response.get("DocEntry") or ""),
			"sap_status": "Posted",
			"sap_error": "",
		})
	except Exception as e:
		log.status = "Failed"
		log.error_message = str(e)[:1000]
		frappe.db.set_value("Marketing Material Request", request.name, {
			"sap_status": "Failed",
			"sap_error": str(e)[:2000],
		})
		frappe.log_error(frappe.get_traceback(), "SAP B1 Marketing Material Request Failed")

	log.insert(ignore_permissions=True)
	frappe.db.commit()
	return log.name


@frappe.whitelist()
def push_cash_requisition(requisition_name):
	"""Push a submitted Cash Requisition to SAP B1 as an A/P Down Payment Request
	(PurchaseDownPayments, service/account based — no item codes)."""
	from frappe.utils import today as _today
	req = frappe.get_doc("Cash Requisition", requisition_name)
	settings = frappe.get_cached_doc("Agriculture Settings")

	# Never post a second Down Payment Request for the same requisition (a
	# duplicate financial document); a prior successful post is final.
	already = frappe.db.exists("SAP B1 Sync Log", {
		"reference_doctype": "Cash Requisition",
		"reference_name": req.name,
		"sync_type": "DownPaymentRequest",
		"status": "Success",
	})
	if already:
		if req.sap_status != "Posted":
			frappe.db.set_value("Cash Requisition", req.name, "sap_status", "Posted")
		return already

	log = frappe.new_doc("SAP B1 Sync Log")
	log.reference_doctype = "Cash Requisition"
	log.reference_name = req.name
	log.sync_type = "DownPaymentRequest"
	log.status = "Pending"

	try:
		if not req.pay_to:
			raise Exception("Pay To (SAP vendor CardCode) is required.")

		lines = []
		for it in req.items:
			amt = flt(it.amount)
			if amt <= 0:
				continue
			# Per-line expense account, falling back to the requisition default.
			account = it.expense_account or req.expense_account
			if not account:
				raise Exception(
					f"No SAP expense account for line '{it.description or it.idx}'. "
					"Set it on the activity, the line, or the requisition default."
				)
			line = {
				"AccountCode": account,
				"ItemDescription": (it.description or "")[:100],
				"LineTotal": amt,
			}
			if req.tax_code:
				line["TaxCode"] = req.tax_code
			lines.append(line)
		if not lines:
			raise Exception("No requisition lines with a positive amount to post.")

		doc_date = str(getdate(req.request_date or _today()))
		comment = f"TFOP Cash Requisition — {req.name}"
		if req.tfop:
			comment += f" for {req.tfop}"
		payload = {
			"CardCode": req.pay_to,
			"DocType": "dDocument_Service",
			"DownPaymentType": "dptRequest",
			"DocDate": doc_date,
			"DocDueDate": doc_date,
			"Comments": comment,
			"DocumentLines": lines,
		}
		log.request_payload = json.dumps(payload, indent=2)
		response = _post_to_sap(settings, "PurchaseDownPayments", payload)
		log.response_text = json.dumps(response, indent=2)[:140000]
		log.status = "Success"
		log.sap_document_number = str(response.get("DocNum") or response.get("DocEntry") or "")

		frappe.db.set_value("Cash Requisition", req.name, {
			"sap_downpayment_number": log.sap_document_number,
			"sap_status": "Posted",
			"sap_error": "",
		})
	except Exception as e:
		log.status = "Failed"
		log.error_message = str(e)[:1000]
		frappe.db.set_value("Cash Requisition", req.name, {
			"sap_status": "Failed",
			"sap_error": str(e)[:2000],
		})
		frappe.log_error(frappe.get_traceback(), "SAP B1 Cash Requisition Failed")

	log.insert(ignore_permissions=True)
	frappe.db.commit()
	return log.name


@frappe.whitelist()
def push_stock_receipt(request_name):
	"""Confirm promoter received materials in SAP B1 as a Goods Receipt."""
	from frappe.utils import today as _today
	request = frappe.get_doc("Demo Garden Material Request", request_name)
	settings = frappe.get_cached_doc("Agriculture Settings")

	log = frappe.new_doc("SAP B1 Sync Log")
	log.reference_doctype = "Demo Garden Material Request"
	log.reference_name = request.name
	log.sync_type = "GoodsReceipt"
	log.status = "Pending"

	try:
		promoter_warehouse = frappe.db.get_value(
			"Field Promoter", request.promoter, "promoter_warehouse"
		) or settings.sap_default_warehouse

		lines = []
		for item in request.items:
			qty = item.quantity_received or item.quantity_issued or item.quantity_requested or 0
			lines.append({
				"ItemCode": item.item or item.item_name,
				"Quantity": float(qty),
				"WarehouseCode": promoter_warehouse or "",
			})

		payload = {
			"DocDate": str(getdate(request.promoter_receipt_date or _today())),
			"Comments": f"Material receipt confirmed — {request.name} (Promoter: {request.promoter})",
			"DocumentLines": lines,
		}
		log.request_payload = json.dumps(payload, indent=2)
		response = _post_to_sap(settings, "InventoryGenEntries", payload)
		log.response_text = json.dumps(response, indent=2)[:140000]
		log.status = "Success"
		log.sap_document_number = str(response.get("DocNum") or response.get("DocEntry") or "")
	except Exception as e:
		log.status = "Failed"
		log.error_message = str(e)[:1000]
		frappe.log_error(frappe.get_traceback(), "SAP B1 Goods Receipt Failed")

	log.insert(ignore_permissions=True)
	frappe.db.commit()
	return log.name


@frappe.whitelist()
def get_stock_transfer_status(request_name):
	"""Fetch the current status of a Stock Transfer Request from SAP B1."""
	request = frappe.get_doc("Demo Garden Material Request", request_name)
	sap_doc_num = getattr(request, "sap_transfer_request_number", None)
	if not sap_doc_num:
		return {"status": "Not pushed to SAP B1 yet"}

	settings = frappe.get_cached_doc("Agriculture Settings")
	try:
		from frappe.utils import nowdate
		base, cookies = _get_session(settings)
		import requests as _requests
		resp = _requests.get(
			f"{base}/InventoryTransferRequests({sap_doc_num})",
			params={"$select": "DocNum,DocStatus,Comments"},
			cookies=cookies, verify=_verify_ssl(settings), timeout=30
		)
		if resp.status_code == 200:
			data = resp.json()
			return {"sap_doc_num": sap_doc_num, "status": data.get("DocStatus"), "raw": data}
		return {"error": f"SAP returned {resp.status_code}"}
	except Exception as e:
		return {"error": str(e)}


# ─── Warehouse helpers ───────────────────────────────────────────────────────
def _resolve_sap_warehouse(erp_warehouse, fallback=None):
	"""Resolve an ERPNext Warehouse name to its SAP B1 warehouse code.

	Admin maps each Warehouse once via the 'SAP B1 Warehouse Code' field.
	Falls back to Agriculture Settings > Fallback SAP Warehouse Code when unset.
	"""
	if erp_warehouse:
		code = frappe.db.get_value("Warehouse", erp_warehouse, "sap_warehouse_code")
		if code:
			return code
	# fallback: explicit arg, then settings global default
	if fallback:
		return fallback
	return frappe.db.get_single_value("Agriculture Settings", "sap_default_warehouse") or ""


def _assert_distinct_sap_warehouses(from_sap, to_sap, ctx=""):
	"""Guard against an invalid stock transfer where source == destination, or
	either side is unresolved. Catches mapping collisions that an ERPNext-level
	from!=to check misses (two ERPNext warehouses mapped to the same SAP code,
	or a blank warehouse falling back to the same default code).

	Raises Exception (caught by the push functions and recorded on the document).
	"""
	if not from_sap:
		raise Exception(
			"Could not resolve a SAP From-Warehouse code. "
			"Set the SAP B1 Warehouse Code on the source warehouse "
			"or the Fallback SAP Warehouse Code in Agriculture Settings." + (f" [{ctx}]" if ctx else "")
		)
	if not to_sap:
		raise Exception(
			"Could not resolve a SAP To-Warehouse code. "
			"Set the SAP B1 Warehouse Code on the destination warehouse." + (f" [{ctx}]" if ctx else "")
		)
	if from_sap == to_sap:
		raise Exception(
			f"From and To warehouse resolve to the same SAP code ('{from_sap}'). "
			"A transfer must move stock between two different warehouses. "
			"Pick a different To Warehouse, or map distinct SAP B1 Warehouse Codes." + (f" [{ctx}]" if ctx else "")
		)


def _get_user_default_warehouse(user=None):
	"""Return the ERPNext Warehouse set on the User record (custom field default_warehouse)."""
	user = user or frappe.session.user
	return frappe.db.get_value("User", user, "default_warehouse")


@frappe.whitelist()
def get_user_default_warehouse():
	"""Client-callable: returns the logged-in user's assigned warehouse (or None)."""
	return _get_user_default_warehouse(frappe.session.user)


@frappe.whitelist()
def get_mmr_warehouse_defaults():
	"""Client-callable: defaults for a new Marketing Material Request.

	Materials ship FROM the central source store TO the requester's own warehouse.
	- to_warehouse   = the logged-in user's Default Warehouse (destination)
	- from_warehouse = the org-wide Default Source Warehouse (source store)
	"""
	return {
		"to_warehouse": _get_user_default_warehouse(frappe.session.user),
		"from_warehouse": frappe.db.get_single_value("Agriculture Settings", "default_source_warehouse"),
	}


# ─── SAP B1 Service Layer plumbing ───────────────────────────────────────────
def _verify_ssl(settings):
	"""
	Whether to verify the SAP B1 Service Layer TLS certificate.
	Controlled by the 'Verify SAP B1 SSL Certificate' setting (default: on).
	Disable ONLY for an internal SAP server using a self-signed certificate.
	"""
	return bool(getattr(settings, "sap_b1_verify_ssl", 1))


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
		verify=_verify_ssl(settings),
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
		verify=_verify_ssl(settings),
		timeout=60,
	)
	if resp.status_code not in (200, 201):
		raise Exception(f"SAP B1 returned {resp.status_code}: {resp.text[:500]}")
	return resp.json()


def _get_all(settings, endpoint, params=None):
	"""
	GET all rows from a SAP B1 Service Layer collection, following @odata.nextLink
	pagination. Returns a flat list of row dicts.
	"""
	import requests

	base, cookies = _get_session(settings)
	url = f"{base}/{endpoint}"
	rows = []
	page = 0
	while url and page < 500:  # hard safety cap
		resp = requests.get(url, params=params if page == 0 else None,
		                    cookies=cookies, verify=_verify_ssl(settings), timeout=60)
		if resp.status_code != 200:
			raise Exception(f"SAP B1 GET {endpoint} returned {resp.status_code}: {resp.text[:300]}")
		body = resp.json()
		rows.extend(body.get("value", []))
		next_link = body.get("@odata.nextLink")
		url = f"{base}/{next_link}" if next_link else None
		page += 1
	return rows


def _resolve_card_code(erp_customer_name):
	"""
	Return the SAP B1 CardCode for an ERPNext Customer.
	Looks up the sap_card_code custom field set during customer sync.
	Raises a clear error if the customer has not been synced from SAP B1 yet,
	rather than letting SAP reject an overly-long ERP name.
	"""
	if not erp_customer_name:
		frappe.throw(_("Order has no stockist — cannot determine SAP B1 CardCode."))
	card_code = frappe.db.get_value("Customer", erp_customer_name, "sap_card_code")
	if not card_code:
		frappe.throw(
			_("Customer '{0}' has no SAP B1 Card Code. "
			  "Run a customer sync from SAP B1 first, or set the SAP B1 Card Code "
			  "manually on the Customer record.").format(erp_customer_name)
		)
	return card_code


def _build_order_payload(order, settings):
	"""Map an ERPNext Order Collection to the SAP B1 Service Layer `Orders` object."""
	card_code = _resolve_card_code(order.stockist)
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
		"DocumentLines": lines,
	}


def _build_payment_payload(order, settings):
	"""Map an Order Collection payment to a SAP B1 IncomingPayments object."""
	card_code = _resolve_card_code(order.stockist)
	return {
		"CardCode": card_code,
		"DocDate": str(getdate(order.collection_date)),
		"CashSum": float(order.payment_amount or 0),
		"CashAccount": getattr(settings, "sap_default_cash_account", "") or "",
		"Remarks": (
			f"Field payment via CyveTech — {order.name} "
			f"(Promoter: {order.promoter_name or order.promoter})"
		),
	}


def _build_goods_issue_payload(request, settings, today_fn):
	"""Map a Demo Garden Material Request to a SAP B1 InventoryGenExits (Goods Issue)."""
	lines = []
	for item in request.items:
		qty = item.quantity_issued or item.quantity_requested or 0
		if not qty:
			continue
		lines.append({
			"ItemCode": item.item or item.item_name,
			"Quantity": float(qty),
			"WarehouseCode": settings.sap_default_warehouse or "",
		})
	return {
		"DocDate": str(getdate(request.issue_date or today_fn())),
		"Comments": (
			f"Demo garden material issue — {request.name} → {request.demo_garden}"
		),
		"DocumentLines": lines,
	}


# ─── SAP → ERPNext: goods-issue receipt ──────────────────────────────────────
#
# When the store fulfils a Marketing Material Request, it posts a SAP B1 Goods
# Issue (InventoryGenExit) that expenses the materials from the source warehouse.
# There is no link field on the Goods Issue, so we match it to the request by
# item + source warehouse + quantity, on/after the request date, and we never
# claim the same Goods Issue for two requests. (SAP B1 SL has no nested $filter,
# so the recent Goods Issues are fetched and matched client-side.)

# How many of the most-recent Goods Issues to scan per poll. Generous so a
# fulfilment is never missed within the polling window; tune up if your SAP
# issues a very high volume of Goods Issues.
_GOODS_ISSUE_SCAN = 300

# NOTE on quantity / UoM: the match requires the SAP issued Quantity to equal the
# requested qty exactly, and the receipt is posted in the request item's UoM. This
# assumes materials are issued in the item's stock UoM (true for these Nos items).
# A genuine UoM mismatch simply won't match (the MMR stays Pending for manual
# review) — it never posts a wrong quantity silently.


def _fetch_recent_goods_issues(settings, top=_GOODS_ISSUE_SCAN, since_date=None):
	"""Return recent Goods Issues (InventoryGenExits), lines inline.

	SAP B1 SL returns DocumentLines inline on the collection GET (no $expand),
	and supports $orderby/$top/$filter. `since_date` (YYYY-MM-DD) narrows to issues
	on/after that date so the window always covers the oldest still-Pending request.
	Pages via @odata.nextLink up to `top` rows.
	"""
	import requests

	base, cookies = _get_session(settings)

	def _run(use_filter):
		url = f"{base}/InventoryGenExits"
		params = {"$orderby": "DocEntry desc", "$top": top}
		if use_filter and since_date:
			params["$filter"] = f"DocDate ge '{since_date}'"
		rows, page, more = [], 0, False
		while url and len(rows) < top and page < 60:
			resp = requests.get(url, params=params if page == 0 else None,
			                    cookies=cookies, verify=_verify_ssl(settings), timeout=60)
			if resp.status_code != 200:
				raise Exception(f"SAP B1 GET InventoryGenExits returned {resp.status_code}: {resp.text[:300]}")
			body = resp.json()
			rows.extend(body.get("value", []))
			nxt = body.get("@odata.nextLink")
			url = f"{base}/{nxt}" if nxt else None
			more = bool(url)
			page += 1
		return rows, more

	# The server-side DocDate filter is only a pre-narrowing optimisation; the
	# authoritative date check is client-side in _match_goods_issue. SAP B1 SL date
	# literals are quirky, so if the filtered query is rejected, fall back to an
	# unfiltered scan rather than failing the whole sync.
	try:
		rows, more = _run(use_filter=True)
	except Exception:
		if since_date:
			rows, more = _run(use_filter=False)
		else:
			raise

	if len(rows) >= top and more:
		# Hit the scan cap with more available — a very old Pending request could
		# fall outside the window. Surface it rather than silently miss it.
		frappe.log_error(
			f"Goods Issue scan hit the {top}-row cap with more available "
			f"(since_date={since_date}); raise _GOODS_ISSUE_SCAN.",
			"SAP Poll — Goods Issue window overflow",
		)
	return rows[:top]


def _claimed_goods_issue_docentries():
	"""DocEntry of every Goods Issue already bound to a received MMR — so the same
	Goods Issue is never claimed by two requests."""
	return {
		d for d in frappe.get_all(
			"Marketing Material Request", pluck="sap_goods_issue_docentry"
		) if d
	}


def _match_goods_issue(mmr, from_sap, goods_issues, claimed_docentries):
	"""Find the Goods Issue that fulfils this MMR. Pure (no SAP calls).

	A match is a SINGLE Goods Issue that, dated on/after the request and not yet
	claimed, covers EVERY MMR item at the source warehouse (from_sap) with a
	matching quantity (all positive lines). Returns (DocNum, DocEntry, DocDate)
	or (None, None, None).
	"""
	expected = {}
	for it in mmr.items:
		if it.item and flt(it.qty):
			expected[it.item] = expected.get(it.item, 0.0) + flt(it.qty)
	if not expected or not from_sap:
		return None, None, None

	req_date = getdate(mmr.request_date) if mmr.request_date else None
	EPS = 0.001

	# Earliest qualifying issue first (the fulfilment is the first issue after
	# the request), so sort the fetched window by DocEntry ascending.
	for gi in sorted(goods_issues, key=lambda r: r.get("DocEntry") or 0):
		doc_entry = str(gi.get("DocEntry") or "")
		if not doc_entry or doc_entry in claimed_docentries:
			continue
		# The issue cannot predate the request. A missing/unparseable DocDate is
		# treated as NOT a match (never bypass the date rule).
		if req_date:
			raw = gi.get("DocDate")
			try:
				gi_date = getdate(raw) if raw else None
			except Exception:
				gi_date = None
			if not gi_date or gi_date < req_date:
				continue
		# Sum issued qty per expected item, only at the source warehouse. A
		# zero/negative (reversal) line on an expected item disqualifies the whole
		# candidate to avoid coincidental net-sum matches.
		issued = {}
		bad_line = False
		for ln in (gi.get("DocumentLines") or []):
			if (ln.get("WarehouseCode") or "") != from_sap:
				continue
			code = ln.get("ItemCode")
			if code in expected:
				q = flt(ln.get("Quantity") or 0)
				if q <= 0:
					bad_line = True
					break
				issued[code] = issued.get(code, 0.0) + q
		if bad_line:
			continue
		# Require EVERY expected item satisfied with a matching quantity.
		if all(abs(issued.get(code, 0.0) - qty) <= EPS for code, qty in expected.items()):
			return str(gi.get("DocNum") or ""), doc_entry, gi.get("DocDate")
	return None, None, None


def poll_mmr_receipts():
	"""Scheduled (hourly): match SAP Goods Issues to posted Material Requests and
	create the ERPNext stock receipt when a fulfilment is found."""
	settings = frappe.get_cached_doc("Agriculture Settings")
	if not settings.sap_b1_enabled:
		return

	pending = frappe.db.get_all(
		"Marketing Material Request",
		filters={"sap_status": "Posted", "receipt_status": "Pending", "docstatus": 1},
		fields=["name", "from_warehouse", "request_date"],
		order_by="creation asc",
	)
	if not pending:
		return

	# Cover the window back to the oldest still-Pending request.
	dates = [r.request_date for r in pending if r.request_date]
	since = str(min(dates)) if dates else None
	try:
		goods_issues = _fetch_recent_goods_issues(settings, since_date=since)
	except Exception as e:
		frappe.log_error(str(e), "SAP Poll — fetch Goods Issues failed")
		return

	claimed = _claimed_goods_issue_docentries()
	for row in pending:
		try:
			mmr = frappe.get_doc("Marketing Material Request", row.name)
			from_sap = _resolve_sap_warehouse(mmr.from_warehouse, settings.sap_default_warehouse)
			doc_num, doc_entry, doc_date = _match_goods_issue(mmr, from_sap, goods_issues, claimed)
			if doc_entry:
				_receive_mmr_materials(mmr, doc_num, doc_entry, doc_date)
				claimed.add(doc_entry)
				frappe.db.commit()
		except Exception as e:
			frappe.db.rollback()
			frappe.log_error(f"MMR {row.name}: {e}", "SAP Poll — MMR receipt failed")
			continue


@frappe.whitelist()
def check_mmr_receipt(mmr_name):
	"""Manual trigger: scan SAP Goods Issues now for one MMR and receive if matched."""
	mmr = frappe.get_doc("Marketing Material Request", mmr_name)
	# Posting a stock receipt is privileged — read access to the MMR is not enough.
	mmr.check_permission("write")
	if mmr.receipt_status == "Received":
		return {"status": "already_received"}

	settings = frappe.get_cached_doc("Agriculture Settings")
	if not settings.sap_b1_enabled:
		return {"status": "disabled"}

	from_sap = _resolve_sap_warehouse(mmr.from_warehouse, settings.sap_default_warehouse)
	if not from_sap:
		return {"status": "no_match", "message": "Could not resolve the source SAP warehouse for this request."}

	try:
		goods_issues = _fetch_recent_goods_issues(
			settings, since_date=str(mmr.request_date) if mmr.request_date else None
		)
	except Exception as e:
		return {"status": "sap_error", "message": str(e)[:300]}

	claimed = _claimed_goods_issue_docentries()
	doc_num, doc_entry, doc_date = _match_goods_issue(mmr, from_sap, goods_issues, claimed)
	if not doc_entry:
		return {
			"status": "no_match",
			"message": (
				"No matching Goods Issue found in SAP yet — looking for an issue of these "
				"items from warehouse '{0}' with matching quantities, dated on/after the request."
			).format(from_sap),
		}

	try:
		_receive_mmr_materials(mmr, doc_num, doc_entry, doc_date)
		frappe.db.commit()
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(f"MMR {mmr.name}: {e}", "SAP Receipt — manual check")
		return {"status": "sap_error", "message": f"Found Goods Issue {doc_num} but the receipt failed: {str(e)[:200]}"}
	return {"status": "received", "stock_entry": frappe.db.get_value("Marketing Material Request", mmr.name, "erp_stock_entry"), "goods_issue": doc_num}


def _receive_mmr_materials(mmr, gi_doc_num="", gi_doc_entry="", gi_doc_date=None):
	"""Create an ERPNext Stock Entry (Material Receipt) at the destination warehouse
	and mark the MMR received — ONLY if the Stock Entry actually posts.

	Idempotent and claim-safe: re-checks under a row lock so one Goods Issue can
	never be received twice or bound to two requests. On any failure it raises so
	the caller rolls back and the MMR stays Pending for the next poll to retry.
	"""
	# Atomic re-check under a row lock on this MMR (serialises a concurrent poll +
	# manual check), and never bind a Goods Issue already claimed by another request.
	current = frappe.db.get_value(
		"Marketing Material Request", mmr.name, "receipt_status", for_update=True
	)
	if current == "Received":
		return
	if gi_doc_entry and frappe.db.exists(
		"Marketing Material Request",
		{"sap_goods_issue_docentry": gi_doc_entry, "name": ["!=", mmr.name]},
	):
		return

	to_wh = mmr.to_warehouse
	if not to_wh:
		frappe.log_error(f"MMR {mmr.name} has no to_warehouse", "SAP Receipt")
		return

	company = (
		frappe.db.get_value("Warehouse", to_wh, "company")
		or _get_default_company()
	)

	stock_items = []
	for item in mmr.items:
		if not item.item or not (item.qty or 0):
			continue
		if not frappe.db.get_value("Item", item.item, "is_stock_item"):
			continue
		stock_items.append({
			"item_code": item.item,
			"qty": flt(item.qty),
			"uom": item.uom or frappe.db.get_value("Item", item.item, "stock_uom") or "Nos",
			"t_warehouse": to_wh,
		})

	receipt = {
		"receipt_status": "Received",
		"received_date": frappe.utils.today(),
		"sap_goods_transfer_number": gi_doc_num or "",
		"sap_goods_issue_docentry": gi_doc_entry or "",
	}

	if not stock_items:
		# Nothing stockable to receive (all non-stock items) — record the match.
		frappe.db.set_value("Marketing Material Request", mmr.name, receipt)
		return

	# Build + submit the receipt. Any failure propagates so the caller rolls back
	# and the MMR is left Pending (the Goods Issue is NOT claimed) to retry later.
	se = frappe.get_doc({
		"doctype": "Stock Entry",
		"stock_entry_type": "Material Receipt",
		"company": company,
		"posting_date": getdate(gi_doc_date) if gi_doc_date else frappe.utils.today(),
		"set_posting_time": 1,
		"remarks": f"SAP B1 goods issued — MMR {mmr.name}"
		           + (f" (SAP Goods Issue {gi_doc_num})" if gi_doc_num else ""),
		"items": stock_items,
	})
	se.insert(ignore_permissions=True)
	se.submit()

	receipt["erp_stock_entry"] = se.name
	frappe.db.set_value("Marketing Material Request", mmr.name, receipt)


@frappe.whitelist()
def test_connection():
	"""Admin helper — verifies SAP B1 credentials from Settings."""
	settings = frappe.get_cached_doc("Agriculture Settings")
	try:
		_get_session(settings)
		return {"ok": True, "message": _("Successfully connected to SAP B1.")}
	except Exception as e:
		return {"ok": False, "message": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
#  INBOUND: pull master data from SAP B1 (Items, Customers, Price Lists)
#  These create/update native ERPNext masters used in Order Collection / Sales Order.
# ═══════════════════════════════════════════════════════════════════════════════

def _sync_log(sync_type, status, count=0, error=""):
	log = frappe.new_doc("SAP B1 Sync Log")
	log.sync_type = sync_type
	log.status = status
	log.reference_doctype = None
	log.response_text = f"{count} record(s) processed."
	log.error_message = error[:1000] if error else ""
	log.insert(ignore_permissions=True)
	return log.name


def _require_enabled(settings):
	if not settings.sap_b1_enabled:
		frappe.throw(_("SAP B1 integration is disabled in Agriculture Settings."))


@frappe.whitelist()
def pull_price_lists():
	"""Pull SAP B1 Price Lists into ERPNext Price List. Returns {PriceListNo: name}."""
	settings = frappe.get_cached_doc("Agriculture Settings")
	_require_enabled(settings)
	count = 0
	mapping = {}
	try:
		rows = _get_all(settings, "PriceLists",
		                params={"$select": "PriceListNo,PriceListName,BasePriceList"})
		for r in rows:
			name = r.get("PriceListName") or f"SAP Price List {r.get('PriceListNo')}"
			if not frappe.db.exists("Price List", name):
				frappe.get_doc({
					"doctype": "Price List", "price_list_name": name,
					"selling": 1, "currency": "UGX",
				}).insert(ignore_permissions=True)
			mapping[r.get("PriceListNo")] = name
			count += 1
		frappe.db.commit()
		_sync_log("Price List", "Success", count)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "SAP B1 Price List Pull")
		_sync_log("Price List", "Failed", count, str(e))
		raise
	return mapping


@frappe.whitelist()
def pull_items(price_map=None):
	"""Pull SAP B1 Items into ERPNext Item, plus their Item Prices."""
	settings = frappe.get_cached_doc("Agriculture Settings")
	_require_enabled(settings)

	item_group = settings.sap_default_item_group or _ensure_item_group()
	default_uom = settings.sap_default_uom or "Nos"
	if price_map is None:
		price_map = pull_price_lists()

	count = 0
	try:
		rows = _get_all(settings, "Items", params={
			"$select": "ItemCode,ItemName,ItemsGroupCode,InventoryItem,SalesItem,ItemPrices",
		})
		for r in rows:
			code = r.get("ItemCode")
			if not code:
				continue
			_upsert_item(code, r, item_group, default_uom)
			_upsert_item_prices(code, r.get("ItemPrices") or [], price_map, settings)
			count += 1
		frappe.db.set_value("Agriculture Settings", "Agriculture Settings",
		                    "last_master_sync", frappe.utils.now())
		frappe.db.commit()
		_sync_log("Item", "Success", count)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "SAP B1 Item Pull")
		_sync_log("Item", "Failed", count, str(e))
		raise
	return count


def _get_default_company():
	"""Return the default company for this ERPNext instance."""
	return (
		frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
		or ""
	)


def _mandatory_custom_fields(doctype):
	"""
	Return a dict of fieldname: default_value for every mandatory custom field
	on the given doctype that we need to satisfy during programmatic inserts.
	Currently handles 'custom_company' universally; extend as needed.
	"""
	mandatory_customs = {}
	custom_fields = frappe.get_all(
		"Custom Field",
		filters={"dt": doctype, "reqd": 1},
		fields=["fieldname", "fieldtype", "options"],
	)
	default_company = _get_default_company()
	for cf in custom_fields:
		fn = cf.fieldname
		# Company link fields
		if cf.fieldtype == "Link" and cf.options == "Company":
			mandatory_customs[fn] = default_company
		# Any other mandatory Link pointing to Company by naming convention
		elif "company" in fn.lower() and cf.fieldtype == "Link":
			mandatory_customs[fn] = default_company
	return mandatory_customs


def _build_item_default(company):
	"""
	Build an item_defaults child row for the given company.
	Introspects mandatory custom fields on the 'Item Default' child table
	(e.g. custom_company) and populates them automatically.
	"""
	row = {"company": company}
	# Find mandatory custom fields on Item Default child table
	child_customs = frappe.get_all(
		"Custom Field",
		filters={"dt": "Item Default", "reqd": 1},
		fields=["fieldname", "fieldtype", "options"],
	)
	for cf in child_customs:
		fn = cf.fieldname
		if cf.fieldtype == "Link" and cf.options == "Company":
			row[fn] = company
		elif "company" in fn.lower() and cf.fieldtype == "Link":
			row[fn] = company
	return row


def _ensure_item_default(doc, company):
	"""
	Ensure the Item document has an item_defaults row for the given company
	with all mandatory custom fields populated. Works for both new and existing docs.
	"""
	row_data = _build_item_default(company)

	# Check if a row already exists for this company
	existing_row = None
	for d in doc.get("item_defaults", []):
		if d.get("company") == company:
			existing_row = d
			break

	if existing_row:
		# Update the existing row with mandatory field values
		for k, v in row_data.items():
			setattr(existing_row, k, v)
	else:
		# Append a fresh row
		doc.append("item_defaults", row_data)


def _upsert_item(code, r, item_group, default_uom):
	name = r.get("ItemName") or code
	is_stock = 1 if (r.get("InventoryItem") == "tYES") else 0
	is_sales = 1 if (r.get("SalesItem") != "tNO") else 0
	company = _get_default_company()

	if frappe.db.exists("Item", code):
		doc = frappe.get_doc("Item", code)
		doc.item_name = name
		doc.is_sales_item = is_sales
		_ensure_item_default(doc, company)
		for fieldname, value in _mandatory_custom_fields("Item").items():
			if not doc.get(fieldname):
				setattr(doc, fieldname, value)
		doc.flags.ignore_permissions = True
		doc.save()
	else:
		payload = {
			"doctype": "Item",
			"item_code": code,
			"item_name": name,
			"item_group": item_group,
			"stock_uom": default_uom,
			"is_stock_item": is_stock,
			"is_sales_item": is_sales,
			"description": name,
			"sap_synced": 1,
			"item_defaults": [_build_item_default(company)],
		}
		# Also handle any mandatory custom fields directly on the Item doctype
		payload.update(_mandatory_custom_fields("Item"))
		frappe.get_doc(payload).insert(ignore_permissions=True)


def _upsert_item_prices(code, item_prices, price_map, settings):
	for p in item_prices:
		rate = p.get("Price")
		if not rate:
			continue
		pl_name = price_map.get(p.get("PriceList")) or settings.sap_default_price_list
		if not pl_name:
			continue
		existing = frappe.db.get_value(
			"Item Price",
			{"item_code": code, "price_list": pl_name, "selling": 1},
			"name",
		)
		if existing:
			frappe.db.set_value("Item Price", existing, "price_list_rate", rate)
		else:
			frappe.get_doc({
				"doctype": "Item Price",
				"item_code": code,
				"price_list": pl_name,
				"price_list_rate": rate,
				"selling": 1,
				"currency": p.get("Currency") or "UGX",
			}).insert(ignore_permissions=True)


@frappe.whitelist()
def pull_customers():
	"""Pull SAP B1 customer Business Partners into ERPNext Customer."""
	settings = frappe.get_cached_doc("Agriculture Settings")
	_require_enabled(settings)

	customer_group = settings.sap_default_customer_group or _ensure_customer_group()
	territory = settings.sap_default_territory or _ensure_territory()

	count = 0
	try:
		rows = _get_all(settings, "BusinessPartners", params={
			"$select": "CardCode,CardName,Phone1,EmailAddress,Currency",
			"$filter": "CardType eq 'cCustomer'",
		})
		for r in rows:
			_upsert_customer(r, customer_group, territory)
			count += 1
		frappe.db.commit()
		_sync_log("Customer", "Success", count)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "SAP B1 Customer Pull")
		_sync_log("Customer", "Failed", count, str(e))
		raise
	return count


def _clean_phone(raw):
	"""
	Return a phone number Frappe will accept, or None.
	SAP B1 sometimes stores values like '393340507/8' (range notation) or
	multiple numbers separated by '/' or ','. We take the first entry and
	strip any characters that are not digits, +, -, (, ), or space.
	"""
	import re
	if not raw:
		return None
	phone = re.split(r"[/,;]", str(raw))[0].strip()
	phone = re.sub(r"[^\d\+\-\(\) ]", "", phone).strip()
	return phone if len(phone) >= 6 else None


def _upsert_customer(r, customer_group, territory):
	card_code = r.get("CardCode")
	card_name = r.get("CardName") or card_code
	if not card_code:
		return
	phone = _clean_phone(r.get("Phone1"))
	# Match on the stored SAP CardCode (custom field) to avoid duplicates
	existing = frappe.db.get_value("Customer", {"sap_card_code": card_code}, "name")
	if existing:
		doc = frappe.get_doc("Customer", existing)
		doc.customer_name = card_name
		doc.mobile_no = phone
		doc.flags.ignore_permissions = True
		doc.save()
	else:
		payload = {
			"doctype": "Customer",
			"customer_name": card_name,
			"customer_group": customer_group,
			"territory": territory,
			"sap_card_code": card_code,
			"mobile_no": phone,
		}
		# Inject mandatory custom fields (e.g. custom_company)
		payload.update(_mandatory_custom_fields("Customer"))
		frappe.get_doc(payload).insert(ignore_permissions=True)


# ── default-master helpers ───────────────────────────────────────────────────
def _ensure_item_group():
	if not frappe.db.exists("Item Group", "SAP Items"):
		frappe.get_doc({"doctype": "Item Group", "item_group_name": "SAP Items",
		                "parent_item_group": "All Item Groups", "is_group": 0}).insert(ignore_permissions=True)
	return "SAP Items"


def _ensure_customer_group():
	if not frappe.db.exists("Customer Group", "Stockists"):
		frappe.get_doc({"doctype": "Customer Group", "customer_group_name": "Stockists",
		                "parent_customer_group": "All Customer Groups", "is_group": 0}).insert(ignore_permissions=True)
	return "Stockists"


def _ensure_territory():
	return "All Territories" if frappe.db.exists("Territory", "All Territories") else frappe.db.get_value("Territory", {"is_group": 0}, "name")


# ── orchestrator ─────────────────────────────────────────────────────────────
@frappe.whitelist()
def sync_masters_from_sap():
	"""Pull everything: Price Lists, Items (+prices), Customers. Scheduler entry point (runs inline)."""
	# Ensure custom fields exist before any sync — handles sites installed before the patch ran
	from agriculture.agriculture.setup import ensure_custom_fields
	ensure_custom_fields()

	result = {}
	price_map = pull_price_lists()
	result["price_lists"] = len(price_map)
	result["items"] = pull_items(price_map=price_map)
	result["customers"] = pull_customers()
	return result


def scheduled_master_sync():
	"""Daily scheduler — only runs if both SAP and auto-sync are enabled."""
	s = frappe.get_cached_doc("Agriculture Settings")
	if s.sap_b1_enabled and s.auto_sync_masters_daily:
		sync_masters_from_sap()


# ── Background job entry points (called by UI buttons, no HTTP timeout) ───────
@frappe.whitelist()
def enqueue_pull_items():
	"""Enqueue item sync as a background job — returns immediately, no timeout."""
	frappe.enqueue(
		"agriculture.agriculture.sap_integration.pull_items",
		queue="long",
		timeout=3600,
		job_name="SAP B1 — Sync Items",
		is_async=True,
	)
	return {"status": "queued", "message": _("Item sync started in the background. Check SAP B1 Sync Log for results.")}


@frappe.whitelist()
def enqueue_pull_customers():
	"""Enqueue customer sync as a background job."""
	frappe.enqueue(
		"agriculture.agriculture.sap_integration.pull_customers",
		queue="long",
		timeout=1800,
		job_name="SAP B1 — Sync Customers",
		is_async=True,
	)
	return {"status": "queued", "message": _("Customer sync started in the background. Check SAP B1 Sync Log for results.")}


@frappe.whitelist()
def enqueue_pull_price_lists():
	"""Enqueue price list sync as a background job."""
	frappe.enqueue(
		"agriculture.agriculture.sap_integration.pull_price_lists",
		queue="long",
		timeout=600,
		job_name="SAP B1 — Sync Price Lists",
		is_async=True,
	)
	return {"status": "queued", "message": _("Price list sync started in the background. Check SAP B1 Sync Log for results.")}


@frappe.whitelist()
def enqueue_sync_all():
	"""Enqueue full master sync (price lists + items + customers) as a single background job."""
	frappe.enqueue(
		"agriculture.agriculture.sap_integration.sync_masters_from_sap",
		queue="long",
		timeout=7200,
		job_name="SAP B1 — Sync All Masters",
		is_async=True,
	)
	return {"status": "queued", "message": _("Full master data sync started in the background. This may take several minutes. Check SAP B1 Sync Log for results.")}

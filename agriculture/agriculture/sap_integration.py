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
		# Get the promoter's warehouse
		promoter_warehouse = frappe.db.get_value(
			"Field Promoter", request.promoter, "promoter_warehouse"
		) or settings.sap_default_warehouse

		lines = []
		for item in request.items:
			lines.append({
				"ItemCode": item.item or item.item_name,
				"Quantity": float(item.quantity_requested or 0),
				"WarehouseCode": settings.sap_default_warehouse or "",
				"ToWarehouseCode": promoter_warehouse or "",
			})

		payload = {
			"DocDate": str(getdate(request.request_date or _today())),
			"Comments": f"Demo material request — {request.name} for {request.demo_garden} (Promoter: {request.promoter})",
			"U_CyveTechRef": request.name,
			"StockTransferLines": lines,
		}
		log.request_payload = json.dumps(payload, indent=2)
		response = _post_to_sap(settings, "StockTransferRequests", payload)
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
			"U_CyveTechRef": request.name,
			"DocumentLines": lines,
		}
		log.request_payload = json.dumps(payload, indent=2)
		response = _post_to_sap(settings, "PurchaseDeliveryNotes", payload)
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
			f"{base}/StockTransferRequests({sap_doc_num})",
			params={"$select": "DocNum,DocStatus,Comments"},
			cookies=cookies, verify=_verify_ssl(settings), timeout=30
		)
		if resp.status_code == 200:
			data = resp.json()
			return {"sap_doc_num": sap_doc_num, "status": data.get("DocStatus"), "raw": data}
		return {"error": f"SAP returned {resp.status_code}"}
	except Exception as e:
		return {"error": str(e)}


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
		"U_CyveTechRef": order.name,
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
		"U_CyveTechRef": order.name,
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
		"U_CyveTechRef": request.name,
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
		# Use direct DB calls to avoid mandatory validation on existing items.
		# custom_company lives on Item Default child rows — patch them via SQL.
		frappe.db.set_value("Item", code, {
			"item_name": name,
			"is_sales_item": is_sales,
		}, update_modified=False)
		_patch_item_defaults_sql(code, company)
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
		payload.update(_mandatory_custom_fields("Item"))
		frappe.get_doc(payload).insert(ignore_permissions=True, ignore_mandatory=True)


def _patch_item_defaults_sql(code, company):
	"""
	Ensure an Item Default row exists for this company with custom_company set.
	Uses direct SQL so mandatory validation on the child table is bypassed.
	"""
	existing = frappe.db.sql(
		"SELECT name FROM `tabItem Default` WHERE parent=%s AND company=%s LIMIT 1",
		(code, company), as_dict=True,
	)
	if existing:
		# Set custom_company (and any other company-link custom field) on the row
		frappe.db.sql(
			"UPDATE `tabItem Default` SET custom_company=%s WHERE parent=%s AND company=%s",
			(company, code, company),
		)
	else:
		row_name = frappe.generate_hash(length=10)
		frappe.db.sql(
			"""INSERT INTO `tabItem Default`
			   (name, parent, parenttype, parentfield, company, custom_company,
			    creation, modified, owner, modified_by, idx)
			   VALUES (%s,%s,'Item','item_defaults',%s,%s,NOW(),NOW(),'Administrator','Administrator',1)""",
			(row_name, code, company, company),
		)


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

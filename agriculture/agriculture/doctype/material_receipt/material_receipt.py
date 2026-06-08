# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt
"""
Material Receipt — canonical "stock received in the field" record.

This doctype is the bridge between the request side (Demo Garden Material
Request) and the actual stock-on-hand record (Promoter Stock Ledger). It can
be used in two modes:

1. **Linked**: created from a Demo Garden Material Request after the store
   marks it Issued. On submit, posts ledger entries AND advances the linked
   Material Request to status=Received + sets the receipt date/flag.

2. **Standalone**: a promoter records materials received outside the formal
   request flow (donated stock, replacement deliveries, etc.) without
   linking to a Material Request.

In both cases, `submit_receipt` posts one Promoter Stock Ledger entry per
items child row and (optionally) pushes a SAP B1 Goods Receipt via the
existing SAP integration.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

# Re-use the canonical ledger poster from the planting record controller —
# keeps balance-calculation logic in one place.
from agriculture.agriculture.doctype.demo_garden_planting_record.demo_garden_planting_record import (
	_post_ledger_entry,
)


class MaterialReceipt(Document):
	def validate(self):
		self._set_gps_text()
		self._validate_items()

	def _set_gps_text(self):
		if self.gps_latitude and self.gps_longitude:
			self.gps_location_text = f"{self.gps_latitude:.6f}, {self.gps_longitude:.6f}"

	def _validate_items(self):
		if not self.items:
			frappe.throw(_("Add at least one item received."))
		for row in self.items:
			if not row.item_name:
				frappe.throw(_("Row {0}: item name is required.").format(row.idx))
			if not row.quantity_received or row.quantity_received <= 0:
				frappe.throw(
					_("Row {0} ('{1}'): quantity received must be greater than 0.").format(
						row.idx, row.item_name))

	# ── Workflow ──────────────────────────────────────────────────────────────
	@frappe.whitelist()
	def submit_receipt(self):
		"""Post receipt entries to the Promoter Stock Ledger and advance the
		linked Material Request (if any) to Received."""
		if self.status != "Draft":
			frappe.throw(_("Only Draft receipts can be submitted"))

		frappe.db.set_value("Material Receipt", self.name, "status", "Submitted")
		self.status = "Submitted"

		# 1) Post to Promoter Stock Ledger
		self._post_to_ledger()

		# 2) Advance the linked Material Request (if any)
		if self.material_request:
			self._advance_material_request()

		# 3) Advance the linked Demo Garden status
		if self.demo_garden:
			current = frappe.db.get_value("Demo Garden", self.demo_garden, "status")
			if current in ("Material Requested", "Registered"):
				frappe.db.set_value(
					"Demo Garden", self.demo_garden, "status", "Material Received")

		# 4) Optional SAP B1 Goods Receipt push (non-fatal if SAP disabled)
		self._maybe_push_sap_goods_receipt()

		frappe.db.commit()
		return "Submitted"

	def _post_to_ledger(self):
		for row in self.items:
			_post_ledger_entry(
				promoter=self.promoter,
				demo_garden=self.demo_garden or "",
				transaction_type="Receipt",
				transaction_date=self.receipt_date or today(),
				product_name=row.item_name,
				uom=row.uom,
				qty_in=row.quantity_received,
				reference_doctype="Material Receipt",
				reference_name=self.name,
			)

	def _advance_material_request(self):
		"""Mark the linked Material Request as Received and stamp its
		promoter_receipt_date. Quantities on the request's items are
		updated from the receipt where possible so the request reflects
		what actually arrived."""
		mr = frappe.get_doc("Demo Garden Material Request", self.material_request)
		# Build a lookup of receipt quantities by item_name (lowercased)
		received_by_name = {}
		for row in self.items:
			key = (row.item_name or "").strip().lower()
			received_by_name[key] = received_by_name.get(key, 0) + (row.quantity_received or 0)

		# Update each request item's quantity_received
		for it in mr.items:
			key = (it.item_name or "").strip().lower()
			if key in received_by_name:
				it.quantity_received = received_by_name[key]
		mr.flags.ignore_permissions = True
		mr.save()

		frappe.db.set_value("Demo Garden Material Request", mr.name, {
			"status": "Received",
			"promoter_receipt_confirmed": 1,
			"promoter_receipt_date": self.receipt_date or today(),
		})

	def _maybe_push_sap_goods_receipt(self):
		"""Best-effort SAP B1 Goods Receipt push. Mirrors the existing
		push_stock_receipt logic but anchored on this Material Receipt's
		linked Material Request (the SAP doc reference)."""
		if not self.material_request:
			return
		try:
			settings = frappe.get_cached_doc("Agriculture Settings")
			if not settings.sap_b1_enabled:
				return
			from agriculture.agriculture.sap_integration import push_stock_receipt
			frappe.enqueue(
				"agriculture.agriculture.sap_integration.push_stock_receipt",
				queue="long",
				request_name=self.material_request,
			)
		except Exception as e:
			frappe.log_error(
				f"SAP Goods Receipt push from Material Receipt {self.name} failed: {e}",
				"Material Receipt SAP Push")


# ── Module-level helpers (used by the mobile app via run_doc_method) ──────────


@frappe.whitelist()
def receive_from_material_request(material_request, receipt_date=None, remarks=None):
	"""Create + submit a Material Receipt that mirrors a Material Request's
	items. Used as a one-tap "Receive Now" shortcut from the mobile app:
	the promoter taps "Receive" on an Issued request, and this method
	creates the formal Material Receipt for them.

	Returns the new Material Receipt name on success.
	"""
	mr = frappe.get_doc("Demo Garden Material Request", material_request)
	if mr.status not in ("Issued", "Approved", "Submitted"):
		frappe.throw(_("Material Request {0} is not awaiting receipt (status: {1}).").format(
			mr.name, mr.status))

	rcpt = frappe.new_doc("Material Receipt")
	rcpt.promoter = mr.promoter
	rcpt.demo_garden = mr.demo_garden
	rcpt.material_request = mr.name
	rcpt.receipt_date = receipt_date or today()
	rcpt.issued_by = mr.issued_by
	rcpt.issue_date = mr.issue_date
	rcpt.remarks = remarks or ""
	for it in mr.items:
		# Prefer quantity_issued if the store recorded one; fall back to
		# quantity_received (set on Approved-without-Issued requests) or
		# quantity_requested for fast-path receipts.
		qty = it.quantity_issued or it.quantity_received or it.quantity_requested or 0
		rcpt.append("items", {
			"item_type": it.item_type,
			"item": it.item,
			"item_name": it.item_name,
			"uom": it.uom,
			"quantity_received": qty,
		})
	rcpt.flags.ignore_permissions = True
	rcpt.insert()
	rcpt.submit_receipt()
	return rcpt.name

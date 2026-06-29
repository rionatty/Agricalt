# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""
Patch: add ERPNext stock tools (Stock Entry, Warehouse, Stock Ledger,
Stock Balance, Stock Projected Qty) to the Agriculture workspace's
"Stock & Inventory" card, in-DB, since migrate won't overwrite an existing
workspace. Idempotent.
"""
import frappe

WORKSPACE = "Agriculture"
ANCHOR = "Promoter Stock Ledger"  # last existing link in the Stock & Inventory card

STOCK_LINKS = [
	{"type": "Link", "label": "Stock Entry", "link_to": "Stock Entry",
	 "link_type": "DocType", "onboard": 0,
	 "description": "Stock receipts/issues (SAP Goods Issue receipts post here)"},
	{"type": "Link", "label": "Warehouse", "link_to": "Warehouse",
	 "link_type": "DocType", "onboard": 0,
	 "description": "Warehouses and their SAP B1 Warehouse Code mapping"},
	{"type": "Link", "label": "Stock Ledger", "link_to": "Stock Ledger",
	 "link_type": "Report", "is_query_report": 1, "onboard": 0,
	 "description": "All stock movements (the stock movement log)"},
	{"type": "Link", "label": "Stock Balance", "link_to": "Stock Balance",
	 "link_type": "Report", "is_query_report": 1, "onboard": 0,
	 "description": "Current stock per item / warehouse"},
	{"type": "Link", "label": "Stock Projected Qty", "link_to": "Stock Projected Qty",
	 "link_type": "Report", "is_query_report": 1, "onboard": 0},
]


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	doc = frappe.get_doc("Workspace", WORKSPACE)

	# Idempotent — bail if the Stock Entry link is already present.
	if any(l.type == "Link" and l.link_to == "Stock Entry" for l in doc.links):
		return

	for link in STOCK_LINKS:
		doc.append("links", link)

	# Move the freshly appended links to sit under the Stock & Inventory card
	# (right after the Promoter Stock Ledger link), falling back to leaving them
	# at the end if that anchor isn't found.
	anchor = next((i for i, l in enumerate(doc.links) if l.link_to == ANCHOR), None)
	if anchor is not None:
		moved = [doc.links.pop() for _ in range(len(STOCK_LINKS))]
		moved.reverse()  # restore original order (pop takes from the end)
		for offset, row in enumerate(moved):
			doc.links.insert(anchor + 1 + offset, row)
		for i, l in enumerate(doc.links):
			l.idx = i + 1

	doc.flags.ignore_permissions = True
	doc.flags.ignore_version = True
	doc.save(ignore_permissions=True)
	frappe.clear_cache()
	frappe.db.commit()

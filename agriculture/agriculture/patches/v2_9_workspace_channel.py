# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""
Patch: add the "Sales & Channel Stock" section (Channel Stock card) to the
Agriculture workspace, directly in the DB, since migrate won't overwrite an
existing workspace. Idempotent.
"""
import json

import frappe

WORKSPACE = "Agriculture"

NEW_LINKS = [
	{"type": "Card Break", "label": "Channel Stock"},
	{"type": "Link", "label": "Channel Stock Movement", "link_to": "Channel Stock Movement",
	 "link_type": "DocType", "onboard": 0,
	 "description": "Move stock between customer warehouses (distributor -> stockist -> farmer)"},
	{"type": "Link", "label": "Customer", "link_to": "Customer",
	 "link_type": "DocType", "onboard": 0,
	 "description": "Channel partners — each customer has its own warehouse"},
	{"type": "Link", "label": "Customer Stock Receipt", "link_to": "Customer Stock Receipt",
	 "link_type": "DocType", "onboard": 0,
	 "description": "Stock mirrored from SAP sales invoices into customer warehouses"},
]

NEW_BLOCKS = [
	{"id": "hdr_channel", "type": "header",
	 "data": {"text": '<span class="h4"><b>Sales & Channel Stock</b></span>', "col": 12}},
	{"id": "card_channel", "type": "card", "data": {"card_name": "Channel Stock", "col": 4}},
]


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	doc = frappe.get_doc("Workspace", WORKSPACE)

	if not any(l.type == "Card Break" and l.label == "Channel Stock" for l in doc.links):
		for link in NEW_LINKS:
			doc.append("links", link)

	try:
		content = json.loads(doc.content or "[]")
	except (ValueError, TypeError):
		content = []
	have_card = any(
		b.get("type") == "card" and b.get("data", {}).get("card_name") == "Channel Stock"
		for b in content
	)
	if not have_card:
		idx = next(
			(i for i, b in enumerate(content)
			 if b.get("type") == "card" and b.get("data", {}).get("card_name") == "Competition"),
			None,
		)
		if idx is None:
			content.extend(NEW_BLOCKS)
		else:
			content[idx + 1:idx + 1] = NEW_BLOCKS
		doc.content = json.dumps(content)

	doc.flags.ignore_permissions = True
	doc.flags.ignore_version = True
	doc.save(ignore_permissions=True)
	frappe.clear_cache()
	frappe.db.commit()

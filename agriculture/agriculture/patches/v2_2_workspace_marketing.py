# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""
Patch: add the Marketing & Campaigns + Competition cards to the Agriculture
workspace, directly in the DB.

`bench migrate` does NOT overwrite an existing Workspace from the app JSON
(it preserves UI customisations), so shipping the cards in the workspace JSON
isn't enough for already-installed sites. This patch mutates the live Workspace
record. It is idempotent — re-running it makes no further changes.
"""
import json

import frappe

WORKSPACE = "Agriculture"

NEW_LINKS = [
	{"type": "Card Break", "label": "Marketing"},
	{"type": "Link", "label": "TFOP", "link_to": "TFOP", "link_type": "DocType", "onboard": 1,
	 "description": "Twiga Farmers Outreach Program — campaign budget"},
	{"type": "Link", "label": "TFOP Actual", "link_to": "TFOP Actual", "link_type": "DocType",
	 "description": "Actual spend posted against a TFOP (budget vs actual)"},
	{"type": "Link", "label": "Marketing Activity Type", "link_to": "Marketing Activity Type", "link_type": "DocType"},
	{"type": "Link", "label": "Marketing Material", "link_to": "Marketing Material", "link_type": "DocType"},
	{"type": "Link", "label": "Budget Category", "link_to": "Budget Category", "link_type": "DocType"},
	{"type": "Card Break", "label": "Competition"},
	{"type": "Link", "label": "Competitor", "link_to": "Competitor", "link_type": "DocType"},
	{"type": "Link", "label": "Competitor Product", "link_to": "Competitor Product", "link_type": "DocType"},
]

NEW_BLOCKS = [
	{"id": "hdr_marketing", "type": "header",
	 "data": {"text": '<span class="h4"><b>Marketing & Campaigns</b></span>', "col": 12}},
	{"id": "card_marketing", "type": "card", "data": {"card_name": "Marketing", "col": 4}},
	{"id": "card_competition", "type": "card", "data": {"card_name": "Competition", "col": 4}},
]


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	doc = frappe.get_doc("Workspace", WORKSPACE)

	# 1. links (child table) — append the card breaks + links once
	if not any(l.type == "Card Break" and l.label == "Marketing" for l in doc.links):
		for link in NEW_LINKS:
			doc.append("links", link)

	# 2. content (layout blocks) — insert header + cards after Orders & Payments
	try:
		content = json.loads(doc.content or "[]")
	except (ValueError, TypeError):
		content = []
	have_card = any(
		b.get("type") == "card" and b.get("data", {}).get("card_name") == "Marketing"
		for b in content
	)
	if not have_card:
		idx = next(
			(i for i, b in enumerate(content)
			 if b.get("type") == "card" and b.get("data", {}).get("card_name") == "Orders & Payments"),
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

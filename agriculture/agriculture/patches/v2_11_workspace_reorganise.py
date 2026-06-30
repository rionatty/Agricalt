# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Reorganise the Agriculture workspace: lead with the CRM modules (Marketing &
Channel Stock), then field ops, demo gardens, events, and a single consolidated
Reports/Masters/Configuration section. Pure layout — reuses the existing cards,
charts, number cards and shortcuts; only the content (section order) changes.
"""
import json

import frappe

WORKSPACE = "Agriculture"

# Desired section layout: (header title, [card_name, ...])
SECTIONS = [
	("Marketing & Channel Stock", ["Marketing", "Competition", "Channel Stock"]),
	("Field Force Management", ["Master Data", "Field Operations", "Orders & Payments"]),
	("Demo Garden Lifecycle", ["Demo Garden Setup", "Demo Garden Operations", "Stock & Inventory"]),
	("Events & Crop Masters", ["Events & Training", "Crops & Lands", "Diseases & Fertilizers"]),
	("Reports, Masters & Configuration", ["Reports", "Configuration", "Integration", "SAP B1 Master Data", "Analytics"]),
]


def _header(title, idx):
	return {"id": f"hdr_re_{idx}", "type": "header",
	        "data": {"text": f'<span class="h4"><b>{title}</b></span>', "col": 12}}


def _rebuild(content):
	# Preserve dashboard (number cards + charts) and quick-access (shortcuts) blocks
	# in their original order; index cards by card_name.
	dash = [b for b in content if b.get("type") in ("number_card", "chart")]
	shortcuts = [b for b in content if b.get("type") == "shortcut"]
	cards = {b.get("data", {}).get("card_name"): b for b in content if b.get("type") == "card"}

	new = [_header("Dashboard", "dash"), *dash,
	       _header("Quick Access", "qa"), *shortcuts]
	for i, (title, names) in enumerate(SECTIONS):
		new.append(_header(title, i))
		for n in names:
			if n in cards:
				new.append(cards[n])
	return new


def execute():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	doc = frappe.get_doc("Workspace", WORKSPACE)
	try:
		content = json.loads(doc.content or "[]")
	except (ValueError, TypeError):
		return
	if not content:
		return
	doc.content = json.dumps(_rebuild(content))
	doc.flags.ignore_permissions = True
	doc.flags.ignore_version = True
	doc.save(ignore_permissions=True)
	frappe.clear_cache()
	frappe.db.commit()

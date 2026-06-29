# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""
Patch: add the Cash Requisition link to the Agriculture workspace (under the
Marketing card, after Marketing Material Request), in-DB, since migrate won't
overwrite an existing workspace. Idempotent.
"""
import frappe


def execute():
	name = "Agriculture"
	if not frappe.db.exists("Workspace", name):
		return
	doc = frappe.get_doc("Workspace", name)
	if any(l.link_type == "DocType" and l.link_to == "Cash Requisition" for l in doc.links):
		return

	link = {
		"type": "Link",
		"label": "Cash Requisition",
		"link_to": "Cash Requisition",
		"link_type": "DocType",
		"onboard": 0,
		"description": "Cash advance for activities/costs -> SAP B1 Down Payment Request",
	}
	# Place under the Marketing card, right after the Marketing Material Request
	# link; fall back to appending if that anchor isn't found.
	anchor = next((i for i, l in enumerate(doc.links) if l.link_to == "Marketing Material Request"), None)
	doc.append("links", link)
	if anchor is not None:
		new_row = doc.links.pop()
		doc.links.insert(anchor + 1, new_row)
		for i, l in enumerate(doc.links):
			l.idx = i + 1

	doc.flags.ignore_permissions = True
	doc.flags.ignore_version = True
	doc.save(ignore_permissions=True)
	frappe.clear_cache()
	frappe.db.commit()

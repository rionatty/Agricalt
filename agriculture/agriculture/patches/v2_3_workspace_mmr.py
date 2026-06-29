# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""
Patch: add the Marketing Material Request link to the Agriculture workspace
(under the Marketing card), in-DB, since migrate won't overwrite an existing
workspace. Idempotent.
"""
import frappe


def execute():
	name = "Agriculture"
	if not frappe.db.exists("Workspace", name):
		return
	doc = frappe.get_doc("Workspace", name)
	if any(l.link_type == "DocType" and l.link_to == "Marketing Material Request" for l in doc.links):
		return

	link = {
		"type": "Link",
		"label": "Marketing Material Request",
		"link_to": "Marketing Material Request",
		"link_type": "DocType",
		"onboard": 0,
	}
	# Insert under the Marketing card (right after the TFOP Actual link); fall back
	# to appending if that anchor isn't found.
	anchor = next((i for i, l in enumerate(doc.links) if l.link_to == "TFOP Actual"), None)
	doc.append("links", link)            # creates a proper child row (at the end)
	if anchor is not None:
		new_row = doc.links.pop()        # take it off the end ...
		doc.links.insert(anchor + 1, new_row)  # ... and place it under Marketing
		for i, l in enumerate(doc.links):
			l.idx = i + 1

	doc.flags.ignore_permissions = True
	doc.flags.ignore_version = True
	doc.save(ignore_permissions=True)
	frappe.clear_cache()
	frappe.db.commit()

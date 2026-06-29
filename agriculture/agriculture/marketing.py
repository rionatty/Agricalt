# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""Marketing module server logic — currently the TFOP approval workflow.

`ensure_tfop_workflow()` is idempotent and is called both from after_install
(setup_agriculture) and from a migrate patch, so the workflow exists on fresh
installs and on already-installed sites.

Approval chain (blueprint approval matrix):
    Draft -> Pending Ops Review -> Pending GM Approval -> Pending Finance -> Approved
with a Reject path from each review state and a Reopen path from Rejected.
"""
import frappe

APPROVAL_ROLES = ["Field Operations Manager", "General Manager", "Finance Manager"]

WORKFLOW_NAME = "TFOP Approval"

# (state, doc_status, allow_edit role, style)
_STATES = [
	("Draft", "0", "Agriculture User", ""),
	("Pending Ops Review", "0", "Field Operations Manager", "Warning"),
	("Pending GM Approval", "0", "General Manager", "Warning"),
	("Pending Finance", "0", "Finance Manager", "Warning"),
	("Approved", "1", "Finance Manager", "Success"),
	("Rejected", "0", "Agriculture User", "Danger"),
]

# (from_state, action, to_state, allowed role)
_TRANSITIONS = [
	("Draft", "Submit for Review", "Pending Ops Review", "Agriculture User"),
	("Pending Ops Review", "Ops Approve", "Pending GM Approval", "Field Operations Manager"),
	("Pending Ops Review", "Reject", "Rejected", "Field Operations Manager"),
	("Pending GM Approval", "GM Approve", "Pending Finance", "General Manager"),
	("Pending GM Approval", "Reject", "Rejected", "General Manager"),
	("Pending Finance", "Release Budget", "Approved", "Finance Manager"),
	("Pending Finance", "Reject", "Rejected", "Finance Manager"),
	("Rejected", "Reopen", "Draft", "Agriculture User"),
]


def ensure_marketing_roles():
	for role in APPROVAL_ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True)


def _grant_tfop_permissions():
	"""Approval roles need write (+ submit for Finance) on TFOP so workflow
	transitions can persist the state change."""
	from frappe.permissions import add_permission, update_permission_property
	for role in APPROVAL_ROLES:
		add_permission("TFOP", role, 0)
		for ptype in ("read", "write"):
			update_permission_property("TFOP", role, 0, ptype, 1)
	# Finance releases the budget (docstatus 0 -> 1) and can cancel.
	for ptype in ("submit", "cancel"):
		update_permission_property("TFOP", "Finance Manager", 0, ptype, 1)


def ensure_tfop_workflow():
	"""Create the roles, workflow states, actions, permissions and the Workflow
	itself if missing. Safe to run repeatedly."""
	ensure_marketing_roles()

	for name, _docstatus, _edit, style in _STATES:
		if not frappe.db.exists("Workflow State", name):
			frappe.get_doc({
				"doctype": "Workflow State",
				"workflow_state_name": name,
				"style": style,
			}).insert(ignore_permissions=True)

	for _from, action, _to, _role in _TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({
				"doctype": "Workflow Action Master",
				"workflow_action_name": action,
			}).insert(ignore_permissions=True)

	_grant_tfop_permissions()

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		return

	wf = frappe.get_doc({
		"doctype": "Workflow",
		"workflow_name": WORKFLOW_NAME,
		"document_type": "TFOP",
		"is_active": 1,
		"override_status": 0,
		"send_email_alert": 0,
		"workflow_state_field": "workflow_state",
		"states": [
			{
				"state": state,
				"doc_status": docstatus,
				"allow_edit": allow_edit,
			}
			for state, docstatus, allow_edit, _style in _STATES
		],
		"transitions": [
			{
				"state": _from,
				"action": action,
				"next_state": _to,
				"allowed": role,
				"allow_self_approval": 1,
			}
			for _from, action, _to, role in _TRANSITIONS
		],
	})
	wf.flags.ignore_permissions = True
	wf.insert(ignore_permissions=True)
	frappe.db.commit()

# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""
Patch: Twiga CRM — TFOP approval workflow.

Creates the approval roles (Field Operations Manager, General Manager, Finance
Manager), the Workflow States / Action Masters, the TFOP permissions, and the
"TFOP Approval" Workflow on existing installs. The TFOP doctypes are imported by
`bench migrate` before this patch runs.
"""

import frappe


def execute():
	from agriculture.agriculture.marketing import ensure_tfop_workflow
	ensure_tfop_workflow()
	frappe.db.commit()

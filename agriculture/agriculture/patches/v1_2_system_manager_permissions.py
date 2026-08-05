# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt
"""
Patch: grant System Manager full access to the custom Agriculture doctypes.

The custom doctypes were created without a System Manager permission row, so a
System-Manager admin (anyone other than the literal Administrator) could not
create records — the '+ Add' button was hidden. Existing sites need this applied.
"""

import frappe


def execute():
	from agriculture.agriculture.setup import grant_system_manager_permissions

	grant_system_manager_permissions()
	frappe.db.commit()

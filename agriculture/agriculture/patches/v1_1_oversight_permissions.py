# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt
"""
Patch: grant Marketing Manager & Store Manager read-level access to the
Agriculture transactional doctypes.

permissions.py treats these roles as see-all (FULL_ACCESS_ROLES), but without
base DocPerms they could not open any records. Existing sites need this applied.
"""

import frappe


def execute():
	from agriculture.agriculture.setup import (
		add_store_manager_permissions,
		create_roles,
		grant_oversight_permissions,
	)

	create_roles()
	add_store_manager_permissions()
	grant_oversight_permissions()
	frappe.db.commit()

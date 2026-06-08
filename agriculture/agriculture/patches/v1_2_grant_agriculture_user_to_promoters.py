# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt
"""
Patch: grant the Agriculture User role to every User linked to a Field Promoter.

Without this role, mobile API writes return HTTP 403 because Frappe's
role-permission gate denies access to the agriculture doctypes. The Field
Promoter controller now auto-grants on save (after_insert / on_update), but
existing Field Promoter records created before this hook need a backfill.
"""

import frappe


def execute():
	if not frappe.db.exists('Role', 'Agriculture User'):
		frappe.get_doc({'doctype': 'Role', 'role_name': 'Agriculture User'}).insert(
			ignore_permissions=True)

	promoters = frappe.get_all(
		'Field Promoter',
		filters={'user': ['is', 'set']},
		fields=['name', 'user'],
	)
	updated = 0
	for p in promoters:
		try:
			u = frappe.get_doc('User', p.user)
			if any(r.role == 'Agriculture User' for r in u.roles):
				continue
			u.append('roles', {'role': 'Agriculture User'})
			u.flags.ignore_permissions = True
			u.save(ignore_permissions=True)
			frappe.clear_cache(user=p.user)
			updated += 1
		except Exception:
			# A missing/disabled User shouldn't break the patch
			continue
	frappe.db.commit()
	print(f'Granted Agriculture User to {updated} promoter user(s).')

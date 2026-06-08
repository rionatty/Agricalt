# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


_AUTO_ROLES = ['Agriculture User']  # baseline for every linked field user


class FieldPromoter(Document):
	def after_insert(self):
		self._create_promoter_warehouse()
		self._ensure_user_roles()

	def on_update(self):
		# Re-run on every save so a later link-edit also grants roles.
		self._ensure_user_roles()

	def _ensure_user_roles(self):
		"""Auto-grant the Agriculture User role to the linked User on save.

		Without this, the mobile app submits a doc as the linked user and gets
		HTTP 403 "User <x> does not have doctype access via role permission".
		Field Promoter is the canonical place to manage this — anyone who is
		a promoter needs to be able to read/write the agriculture doctypes.
		Idempotent: skips users that already have the role.
		"""
		if not self.user:
			return
		try:
			u = frappe.get_doc('User', self.user)
			existing = {r.role for r in u.roles}
			added = []
			for role in _AUTO_ROLES:
				if role in existing:
					continue
				# Make sure the role itself exists (created in setup.py:create_roles)
				if not frappe.db.exists('Role', role):
					frappe.get_doc({'doctype': 'Role', 'role_name': role}).insert(
						ignore_permissions=True)
				u.append('roles', {'role': role})
				added.append(role)
			if added:
				u.flags.ignore_permissions = True
				u.save(ignore_permissions=True)
				frappe.clear_cache(user=self.user)
		except Exception as e:
			# Non-fatal — promoter save must not be blocked by user-role failures
			frappe.log_error(
				f'Could not auto-grant roles to {self.user}: {e}',
				'Field Promoter Auto-Role')

	def _create_promoter_warehouse(self):
		"""
		Auto-create an ERPNext Warehouse for this promoter when they are registered.
		The warehouse tracks demo materials issued to / held by this promoter.
		"""
		warehouse_name = f"{self.promoter_name} - Promoter Store"
		if frappe.db.exists("Warehouse", {"warehouse_name": warehouse_name}):
			existing = frappe.db.get_value("Warehouse", {"warehouse_name": warehouse_name}, "name")
			frappe.db.set_value("Field Promoter", self.name, "promoter_warehouse", existing)
			return

		try:
			company = (
				frappe.db.get_single_value("Global Defaults", "default_company")
				or frappe.db.get_value("Company", {}, "name")
				or ""
			)
			parent_warehouse = frappe.db.get_value(
				"Warehouse", {"is_group": 1, "company": company}, "name"
			) or "All Warehouses"

			doc = frappe.get_doc({
				"doctype": "Warehouse",
				"warehouse_name": warehouse_name,
				"parent_warehouse": parent_warehouse,
				"company": company,
				"warehouse_type": "Transit",
				"is_group": 0,
			})
			doc.flags.ignore_permissions = True
			doc.insert()
			frappe.db.set_value("Field Promoter", self.name, "promoter_warehouse", doc.name)
			frappe.db.commit()
		except Exception as e:
			# Non-fatal — warehouse creation failure should not block promoter save
			frappe.log_error(
				f"Could not create warehouse for promoter {self.name}: {e}",
				"Promoter Warehouse Creation"
			)

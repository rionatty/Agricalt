# Copyright (c) 2026, CyveTech and contributors
# For license information, please see license.txt
"""
Patch: Twiga CRM Phase 0 — Masters.

Re-runs ensure_custom_fields() so existing installs gain the new Twiga master
extension fields:
  * Item.division, Item.is_mineral_salt
  * Customer.is_distributor, Customer.crm_warehouse
  * Territory.territory_level
  * Crop.crop_category, Crop.applicable_season
  * Disease.pest_type, Disease.affected_crops, Disease.recommended_products

The new config-master doctypes (Movement Type, Competitor, Issue Type, ...) and
the new child tables are imported automatically by `bench migrate` before this
patch runs, so the Table custom fields on Disease resolve correctly.
"""

import frappe


def execute():
	from agriculture.agriculture.setup import create_roles, ensure_custom_fields
	create_roles()
	ensure_custom_fields()
	frappe.db.commit()

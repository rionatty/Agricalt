# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt
"""
Row-level security for the Syova Seeds field operations system.

Visibility rules:
  - System Manager / Agriculture Manager / Marketing Manager / Store Manager
      → see ALL records (management, supervisors, store, marketing).
  - Agriculture User (Field Promoter)
      → see ONLY records linked to their own Field Promoter.
  - A promoter who is a supervisor (has subordinates) additionally sees their
      whole team's records.

The link from a User to a Field Promoter is the Field Promoter.user field.
"""

import frappe

# Roles that bypass row filtering and see everything
FULL_ACCESS_ROLES = {
	"System Manager",
	"Administrator",
	"Agriculture Manager",
	"Marketing Manager",
	"Store Manager",
}

# Doctype → fieldname that holds the owning Field Promoter
PROMOTER_FIELD = {
	"Field Activity Log": "promoter",
	"Activity Plan": "promoter",
	"Demo Garden": "responsible_promoter",
	"Demo Garden Material Request": "promoter",
	"Demo Garden Planting Record": "promoter",
	"Demo Garden Input Application": "promoter",
	"Demo Garden Monitoring Visit": "promoter",
	"Demo Garden Field Day": "promoter",
	"Farmer Training Event": "promoter",
	"Order Collection": "promoter",
	"Promoter Stock Ledger": "promoter",
	"Promoter KPI Target": "promoter",
	"Promoter Task": "promoter",
}


def _user_has_full_access(user):
	roles = set(frappe.get_roles(user))
	return bool(roles & FULL_ACCESS_ROLES)


def get_user_promoter(user):
	"""Return the Field Promoter name linked to this user, or None."""
	return frappe.db.get_value("Field Promoter", {"user": user}, "name")


def get_team_promoters(promoter):
	"""Return this promoter plus all promoters who report to them (one level)."""
	team = [promoter]
	subordinates = frappe.get_all(
		"Field Promoter", filters={"supervisor": promoter}, pluck="name"
	)
	team.extend(subordinates)
	return team


def _visible_promoters(user):
	"""List of Field Promoter names this user is allowed to see, or None for all."""
	if _user_has_full_access(user):
		return None  # no restriction
	promoter = get_user_promoter(user)
	if not promoter:
		return []  # not a promoter, no full access → see nothing
	return get_team_promoters(promoter)


def make_query_condition(doctype):
	"""Factory producing a permission_query_conditions function for a doctype."""
	field = PROMOTER_FIELD[doctype]

	def _conditions(user=None):
		user = user or frappe.session.user
		visible = _visible_promoters(user)
		if visible is None:
			return ""  # full access — no filter
		if not visible:
			return "1=0"  # see nothing
		quoted = ", ".join(frappe.db.escape(p) for p in visible)
		return f"`tab{doctype}`.`{field}` in ({quoted})"

	return _conditions


def make_has_permission(doctype):
	"""Factory producing a has_permission function for a doctype."""
	field = PROMOTER_FIELD[doctype]

	def _has_permission(doc, user=None, permission_type=None):
		user = user or frappe.session.user
		visible = _visible_promoters(user)
		if visible is None:
			return True
		if not visible:
			return False
		return doc.get(field) in visible

	return _has_permission


# Concrete callables referenced from hooks.py -------------------------------------

def _build():
	q, h = {}, {}
	for dt in PROMOTER_FIELD:
		q[dt] = make_query_condition(dt)
		h[dt] = make_has_permission(dt)
	return q, h


_QUERY, _HASPERM = _build()


# Per-doctype query-condition entry points (hooks reference these by path)
def field_activity_log_query(user=None): return _QUERY["Field Activity Log"](user)
def activity_plan_query(user=None): return _QUERY["Activity Plan"](user)
def demo_garden_query(user=None): return _QUERY["Demo Garden"](user)
def material_request_query(user=None): return _QUERY["Demo Garden Material Request"](user)
def planting_record_query(user=None): return _QUERY["Demo Garden Planting Record"](user)
def input_application_query(user=None): return _QUERY["Demo Garden Input Application"](user)
def monitoring_visit_query(user=None): return _QUERY["Demo Garden Monitoring Visit"](user)
def field_day_query(user=None): return _QUERY["Demo Garden Field Day"](user)
def training_event_query(user=None): return _QUERY["Farmer Training Event"](user)
def order_collection_query(user=None): return _QUERY["Order Collection"](user)
def stock_ledger_query(user=None): return _QUERY["Promoter Stock Ledger"](user)
def kpi_target_query(user=None): return _QUERY["Promoter KPI Target"](user)
def promoter_task_query(user=None): return _QUERY["Promoter Task"](user)


# Per-doctype has_permission entry points
def field_activity_log_perm(doc, user=None, permission_type=None): return _HASPERM["Field Activity Log"](doc, user)
def activity_plan_perm(doc, user=None, permission_type=None): return _HASPERM["Activity Plan"](doc, user)
def demo_garden_perm(doc, user=None, permission_type=None): return _HASPERM["Demo Garden"](doc, user)
def material_request_perm(doc, user=None, permission_type=None): return _HASPERM["Demo Garden Material Request"](doc, user)
def planting_record_perm(doc, user=None, permission_type=None): return _HASPERM["Demo Garden Planting Record"](doc, user)
def input_application_perm(doc, user=None, permission_type=None): return _HASPERM["Demo Garden Input Application"](doc, user)
def monitoring_visit_perm(doc, user=None, permission_type=None): return _HASPERM["Demo Garden Monitoring Visit"](doc, user)
def field_day_perm(doc, user=None, permission_type=None): return _HASPERM["Demo Garden Field Day"](doc, user)
def training_event_perm(doc, user=None, permission_type=None): return _HASPERM["Farmer Training Event"](doc, user)
def order_collection_perm(doc, user=None, permission_type=None): return _HASPERM["Order Collection"](doc, user)
def stock_ledger_perm(doc, user=None, permission_type=None): return _HASPERM["Promoter Stock Ledger"](doc, user)
def kpi_target_perm(doc, user=None, permission_type=None): return _HASPERM["Promoter KPI Target"](doc, user)
def promoter_task_perm(doc, user=None, permission_type=None): return _HASPERM["Promoter Task"](doc, user)

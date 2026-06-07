# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt
"""
Scheduled background tasks for the Syova Seeds field operations system.
All thresholds are read from Agriculture Settings (admin-configurable).
"""

import frappe
from frappe import _
from frappe.utils import add_days, get_weekday, getdate, today


def _settings():
	return frappe.get_cached_doc("Agriculture Settings")


def _notify(recipients, subject, message, doctype=None, docname=None):
	"""Send via the channels enabled in settings (email and/or in-app)."""
	s = _settings()
	recipients = [r for r in recipients if r]
	if not recipients:
		return

	if s.enable_email_notifications:
		frappe.sendmail(recipients=recipients, subject=subject, message=message)

	if s.enable_inapp_notifications:
		for user in recipients:
			notif = frappe.new_doc("Notification Log")
			notif.subject = subject
			notif.email_content = message
			notif.for_user = user
			notif.type = "Alert"
			if doctype and docname:
				notif.document_type = doctype
				notif.document_name = docname
			notif.insert(ignore_permissions=True)


def _promoter_email(promoter):
	return frappe.db.get_value("Field Promoter", promoter, "email_id")


def _supervisor_email(promoter):
	sup = frappe.db.get_value("Field Promoter", promoter, "supervisor")
	return frappe.db.get_value("Field Promoter", sup, "email_id") if sup else None


# ─── 1. Harvest / field day approaching ──────────────────────────────────────
def send_demo_garden_harvest_alerts():
	lead = int(_settings().harvest_alert_lead_days or 7)
	target_date = add_days(today(), lead)

	gardens = frappe.get_all(
		"Demo Garden",
		filters={
			"status": ["not in", ["Field Day Done", "Completed"]],
			"expected_harvest_date": ["between", [today(), target_date]],
		},
		fields=["name", "demo_garden_name", "responsible_promoter", "expected_harvest_date", "status"],
	)
	for g in gardens:
		_notify(
			[_promoter_email(g.responsible_promoter), _supervisor_email(g.responsible_promoter)],
			_("Harvest / Field Day Approaching: {0}").format(g.demo_garden_name),
			_("Demo Garden <b>{0}</b> has an expected harvest / field day on <b>{1}</b> (status: {2}). "
			  "Please prepare and record the field day event.").format(
				g.demo_garden_name, g.expected_harvest_date, g.status),
			"Demo Garden", g.name,
		)


# ─── 2. Materials received but planting not recorded ─────────────────────────
def alert_unreported_materials():
	days = int(_settings().unreported_material_days or 7)
	threshold = add_days(today(), -days)

	pending = frappe.get_all(
		"Demo Garden Material Request",
		filters={"status": "Received", "promoter_receipt_date": ["<=", threshold]},
		fields=["name", "promoter", "demo_garden", "promoter_receipt_date"],
	)
	for req in pending:
		if frappe.db.get_value("Demo Garden", req.demo_garden, "planting_date"):
			continue
		_notify(
			[_supervisor_email(req.promoter), _promoter_email(req.promoter)],
			_("Materials Received but Planting Not Recorded — {0}").format(req.demo_garden),
			_("Materials for Demo Garden <b>{0}</b> were received on {1} but planting is not yet recorded. "
			  "Request: {2}").format(req.demo_garden, req.promoter_receipt_date, req.name),
			"Demo Garden Material Request", req.name,
		)


# ─── 3. Materials received but inputs not applied (NEW) ───────────────────────
def alert_unapplied_inputs():
	days = int(_settings().unapplied_input_days or 10)
	threshold = add_days(today(), -days)

	# Demo gardens planted but past threshold with no input application recorded
	planted = frappe.get_all(
		"Demo Garden",
		filters={"status": ["in", ["Planted", "Monitoring"]], "planting_date": ["<=", threshold]},
		fields=["name", "demo_garden_name", "responsible_promoter", "planting_date"],
	)
	for g in planted:
		has_inputs = frappe.db.exists(
			"Demo Garden Input Application",
			{"demo_garden": g.name, "status": "Submitted"},
		)
		if has_inputs:
			continue
		_notify(
			[_supervisor_email(g.responsible_promoter), _promoter_email(g.responsible_promoter)],
			_("No Inputs Applied — {0}").format(g.demo_garden_name),
			_("Demo Garden <b>{0}</b> was planted on {1} but no chemical/fertiliser application "
			  "has been recorded. Please follow up.").format(g.demo_garden_name, g.planting_date),
			"Demo Garden", g.name,
		)


# ─── 4. Planned activity not executed (NEW) ──────────────────────────────────
def _find_actual_log(promoter, item, window_start, check_date):
	"""Find an unlinked Field Activity Log that fulfils a planned item.

	A planned visit to a specific Farmer is fulfilled by an actual visit to that
	same farmer any day from the plan start up to the check date (so a visit done
	off the planned day still counts); otherwise match by activity type on the
	planned day.
	"""
	common = {"promoter": promoter, "activity_plan": ["is", "not set"]}
	if item.get("farmer"):
		rows = frappe.get_all("Field Activity Log", filters=dict(common,
			farmer=item.farmer, activity_type=item.activity_type,
			activity_date=["between", [window_start, check_date]]), pluck="name", limit=1)
	else:
		rows = frappe.get_all("Field Activity Log", filters=dict(common,
			activity_type=item.activity_type, activity_date=check_date), pluck="name", limit=1)
	return rows[0] if rows else None


def alert_planned_not_executed():
	if not _settings().plan_vs_actual_check:
		return
	# Reconcile yesterday's planned activities against the actual activity logs.
	check_date = add_days(today(), -1)

	plans = frappe.get_all(
		"Activity Plan",
		filters={"status": "Approved", "from_date": ["<=", check_date], "to_date": [">=", check_date]},
		fields=["name", "promoter", "from_date"],
	)
	for plan in plans:
		planned_items = frappe.get_all(
			"Activity Plan Item",
			filters={"parent": plan.name, "planned_date": check_date},
			fields=["name", "activity_type", "farmer", "execution_status"],
		)
		missed = []
		for item in planned_items:
			if item.execution_status == "Done":
				continue
			log = _find_actual_log(plan.promoter, item, plan.from_date, check_date)
			if log:
				frappe.db.set_value("Activity Plan Item", item.name, {
					"execution_status": "Done",
					"actual_date": check_date,
					"field_activity_log": log,
				})
				frappe.db.set_value("Field Activity Log", log,
					{"activity_plan": plan.name, "is_planned": 1})
				from agriculture.agriculture.doctype.activity_plan.activity_plan import (
					complete_linked_task,
				)
				complete_linked_task(item.name, check_date)
			else:
				frappe.db.set_value("Activity Plan Item", item.name, "execution_status", "Missed")
				missed.append(item.activity_type)

		# Ad-hoc visits done that day that were not part of any plan ("off-plan")
		off_plan = frappe.db.count("Field Activity Log", {
			"promoter": plan.promoter,
			"activity_date": check_date,
			"activity_plan": ["is", "not set"],
		})

		if missed or off_plan:
			parts = []
			if missed:
				parts.append(_("missed {0} planned ({1})").format(len(missed), ", ".join(missed)))
			if off_plan:
				parts.append(_("{0} off-plan visit(s)").format(off_plan))
			_notify(
				[_supervisor_email(plan.promoter), _promoter_email(plan.promoter)],
				_("Plan vs Actual — {0}").format(check_date),
				_("Promoter on {0} (plan {1}): {2}.").format(check_date, plan.name, "; ".join(parts)),
				"Activity Plan", plan.name,
			)


# ─── 5. Weekly plan not submitted ────────────────────────────────────────────
def alert_missing_weekly_plans():
	deadline_day = _settings().weekly_plan_deadline_day or "Sunday"
	# Fire the day AFTER the deadline
	day_after = {
		"Sunday": "Monday", "Monday": "Tuesday", "Tuesday": "Wednesday",
		"Wednesday": "Thursday", "Thursday": "Friday", "Friday": "Saturday",
		"Saturday": "Sunday",
	}[deadline_day]
	if get_weekday() != day_after:
		return

	week_start = today()
	week_end = add_days(today(), 6)
	for p in frappe.get_all("Field Promoter", filters={"status": "Active"},
	                        fields=["name", "promoter_name", "email_id"]):
		exists = frappe.get_all("Activity Plan", filters={
			"promoter": p.name, "from_date": [">=", week_start],
			"plan_type": "Weekly",
			"status": ["in", ["Submitted", "Approved"]],
		})
		if exists:
			continue
		sup_email = _supervisor_email(p.name)
		recipients = [r for r in [p.email_id, sup_email] if r]
		if not recipients:
			continue
		_notify(
			recipients,
			_("Reminder: Submit Your Weekly Activity Plan"),
			_("Dear {0}, you have not submitted an activity plan for {1} to {2}. "
			  "Please submit it as soon as possible.").format(p.promoter_name, week_start, week_end),
		)

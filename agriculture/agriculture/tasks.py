# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt
"""
Scheduled background tasks for the Agriculture / Syova Seeds field operations system.
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today


def send_demo_garden_harvest_alerts():
	"""
	Daily: Alert promoter & supervisor when demo garden harvest/field day date
	is approaching (within 7 days) and the garden is still active.
	"""
	alert_window = 7  # days — TODO: make this configurable in System Settings
	target_date = add_days(today(), alert_window)

	gardens = frappe.get_all(
		"Demo Garden",
		filters={
			"status": ["not in", ["Field Day Done", "Completed"]],
			"expected_harvest_date": ["between", [today(), target_date]],
		},
		fields=["name", "demo_garden_name", "responsible_promoter", "expected_harvest_date", "status"],
	)

	for garden in gardens:
		_notify_harvest_approaching(garden)


def _notify_harvest_approaching(garden):
	promoter = frappe.get_doc("Field Promoter", garden.responsible_promoter)
	recipients = []
	if promoter.email_id:
		recipients.append(promoter.email_id)
	if promoter.supervisor:
		sup_email = frappe.db.get_value("Field Promoter", promoter.supervisor, "email_id")
		if sup_email:
			recipients.append(sup_email)
	if not recipients:
		return
	frappe.sendmail(
		recipients=recipients,
		subject=_("Harvest / Field Day Approaching: {0}").format(garden.demo_garden_name),
		message=_(
			"Demo Garden <b>{0}</b> has an expected harvest / field day date of <b>{1}</b>.<br><br>"
			"Current Status: {2}<br>"
			"Please ensure all preparations are in place and record the field day event in the system."
		).format(garden.demo_garden_name, garden.expected_harvest_date, garden.status),
	)


def alert_unreported_materials():
	"""
	Daily: Alert supervisor when a promoter has received materials but has NOT
	recorded planting or input application after 7 days.
	"""
	threshold_date = add_days(today(), -7)

	pending = frappe.get_all(
		"Demo Garden Material Request",
		filters={
			"status": "Received",
			"promoter_receipt_date": ["<=", threshold_date],
		},
		fields=["name", "promoter", "demo_garden", "promoter_receipt_date"],
	)

	for req in pending:
		# Check if planting has been recorded
		garden = frappe.get_doc("Demo Garden", req.demo_garden)
		if garden.planting_date:
			continue  # planting recorded — no alert needed

		promoter = frappe.get_doc("Field Promoter", req.promoter)
		if not promoter.supervisor:
			continue
		sup_email = frappe.db.get_value("Field Promoter", promoter.supervisor, "email_id")
		if not sup_email:
			continue
		frappe.sendmail(
			recipients=[sup_email],
			subject=_("Materials Received but Planting Not Recorded — {0}").format(req.demo_garden),
			message=_(
				"Field Promoter <b>{0}</b> received materials for Demo Garden <b>{1}</b> on {2} "
				"but has not yet recorded planting.<br><br>"
				"Material Request: {3}"
			).format(
				promoter.promoter_name, req.demo_garden,
				req.promoter_receipt_date, req.name,
			),
		)


def alert_missing_weekly_plans():
	"""
	Daily (runs Monday): Alert promoters who have not submitted a weekly plan by
	end of Sunday for the coming week.
	"""
	from frappe.utils import get_weekday
	if get_weekday() != "Monday":
		return

	all_promoters = frappe.get_all(
		"Field Promoter",
		filters={"status": "Active"},
		fields=["name", "promoter_name", "email_id"],
	)

	week_start = today()
	week_end = add_days(today(), 6)

	for promoter in all_promoters:
		existing = frappe.get_all(
			"Activity Plan",
			filters={
				"promoter": promoter.name,
				"from_date": [">=", week_start],
				"status": ["in", ["Submitted", "Approved"]],
			},
		)
		if existing or not promoter.email_id:
			continue
		frappe.sendmail(
			recipients=[promoter.email_id],
			subject=_("Reminder: Submit Your Weekly Activity Plan"),
			message=_(
				"Dear {0},<br><br>"
				"You have not submitted an activity plan for the week of {1} to {2}.<br>"
				"Please submit your plan in the system as soon as possible."
			).format(promoter.promoter_name, week_start, week_end),
		)

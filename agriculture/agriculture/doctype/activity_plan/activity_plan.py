# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

APPROVER_ROLES = {"Agriculture Manager", "System Manager", "Administrator"}
_WEEKDAY_CODES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


class ActivityPlan(Document):
	def validate(self):
		self.validate_dates()
		self.validate_activity_dates()
		self.validate_no_overlap()

	def validate_dates(self):
		if self.from_date and self.to_date and getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(_("To Date must be after From Date"))

	def validate_activity_dates(self):
		"""Keep every planned activity inside the plan window and auto-fill its weekday."""
		for row in self.activities:
			if not row.planned_date:
				continue
			pdate = getdate(row.planned_date)
			if self.from_date and pdate < getdate(self.from_date):
				frappe.throw(_("Row {0}: planned date {1} is before the plan start ({2}).").format(
					row.idx, row.planned_date, self.from_date))
			if self.to_date and pdate > getdate(self.to_date):
				frappe.throw(_("Row {0}: planned date {1} is after the plan end ({2}).").format(
					row.idx, row.planned_date, self.to_date))
			row.day_of_week = _WEEKDAY_CODES[pdate.weekday()]

	def validate_no_overlap(self):
		"""Prevent two plans of the same type overlapping for one promoter.

		Weekly and Monthly plans are allowed to overlap (a month contains its
		weeks); two plans of the *same* type for the same period are not.
		"""
		if not (self.promoter and self.from_date and self.to_date):
			return
		dup = frappe.get_all("Activity Plan", filters={
			"name": ["!=", self.name],
			"promoter": self.promoter,
			"plan_type": self.plan_type,
			"status": ["!=", "Rejected"],
			"from_date": ["<=", self.to_date],
			"to_date": [">=", self.from_date],
		}, pluck="name", limit=1)
		if dup:
			frappe.throw(_("Overlapping {0} plan {1} already exists for this promoter.").format(
				self.plan_type or "", dup[0]))

	# ── Workflow ──────────────────────────────────────────────────────────────
	@frappe.whitelist()
	def submit_for_approval(self):
		if self.status != "Draft":
			frappe.throw(_("Only Draft plans can be submitted for approval"))
		if not self.activities:
			frappe.throw(_("Add at least one planned activity before submitting"))
		frappe.db.set_value("Activity Plan", self.name, "status", "Submitted")
		self.status = "Submitted"
		self.notify_supervisor()
		return "Submitted"

	@frappe.whitelist()
	def approve(self):
		_ensure_can_approve()
		if self.status != "Submitted":
			frappe.throw(_("Only Submitted plans can be approved"))
		frappe.db.set_value("Activity Plan", self.name, {
			"status": "Approved",
			"approved_by": frappe.session.user,
			"approval_date": today(),
		})
		frappe.db.commit()
		self.status = "Approved"
		created = self._generate_tasks()
		self._notify_promoter(
			_("Activity Plan Approved: {0}").format(self.name),
			_("Your activity plan {0} ({1} to {2}) has been approved. "
			  "{3} task(s) were added to your task list.").format(
				self.name, self.from_date, self.to_date, created),
		)
		return "Approved"

	def _generate_tasks(self):
		"""Create one Promoter Task per planned activity (idempotent per plan item).

		The plan becomes the promoter's actionable task list; each task links back
		to its Activity Plan Item so completing either side reconciles the other.
		Returns the number of tasks created.
		"""
		created = 0
		for item in self.activities:
			if not item.planned_date:
				continue
			if frappe.db.exists("Promoter Task", {"activity_plan_item": item.name}):
				continue
			subject = item.activity_type or _("Planned activity")
			contact = item.get("farmer_name") or item.location
			if contact:
				subject = f"{subject} — {contact}"
			task = frappe.get_doc({
				"doctype": "Promoter Task",
				"subject": subject,
				"promoter": self.promoter,
				"status": "Open",
				"priority": "Medium",
				"due_date": item.planned_date,
				"task_type": _TASK_TYPE_MAP.get(item.activity_type, "Other"),
				"farmer": item.get("farmer"),
				"description": item.get("purpose"),
				"activity_plan": self.name,
				"activity_plan_item": item.name,
				"assigned_by": frappe.session.user,
			})
			task.flags.skip_assignee_notification = True
			task.flags.ignore_permissions = True
			task.insert()
			created += 1
		return created

	@frappe.whitelist()
	def reject(self, reason=""):
		_ensure_can_approve()
		if self.status not in ("Submitted", "Draft"):
			frappe.throw(_("Only Submitted plans can be rejected"))
		frappe.db.set_value("Activity Plan", self.name, {
			"status": "Rejected",
			"rejection_reason": reason,
		})
		frappe.db.commit()
		self._notify_promoter(
			_("Activity Plan Rejected: {0}").format(self.name),
			_("Your activity plan {0} was rejected. Reason: {1}").format(self.name, reason or "—"),
		)
		return "Rejected"

	@frappe.whitelist()
	def revise(self):
		"""Send a rejected plan back to Draft so the promoter can edit and resubmit."""
		if self.status != "Rejected":
			frappe.throw(_("Only Rejected plans can be revised"))
		frappe.db.set_value("Activity Plan", self.name, {"status": "Draft", "rejection_reason": ""})
		return "Draft"

	# ── Notifications ─────────────────────────────────────────────────────────
	def notify_supervisor(self):
		"""Notify the promoter's supervisor that a plan awaits approval."""
		from agriculture.agriculture.tasks import _notify
		promoter = frappe.get_doc("Field Promoter", self.promoter)
		if not promoter.supervisor:
			return
		sup_email = frappe.db.get_value("Field Promoter", promoter.supervisor, "email_id")
		if not sup_email:
			return
		_notify(
			[sup_email],
			_("Activity Plan Submitted for Approval: {0}").format(self.name),
			_("Field Promoter {0} has submitted Activity Plan {1} ({2} to {3}) for your approval.").format(
				promoter.promoter_name, self.name, self.from_date, self.to_date),
			"Activity Plan", self.name,
		)

	def _notify_promoter(self, subject, message):
		"""Notify the plan's promoter (settings-aware: email and/or in-app)."""
		from agriculture.agriculture.tasks import _notify
		email = frappe.db.get_value("Field Promoter", self.promoter, "email_id")
		if email:
			_notify([email], subject, message, "Activity Plan", self.name)


_TASK_TYPE_MAP = {
	"Farm Visit": "Farm Visit",
	"Stockist Visit": "Stockist Visit",
	"Farmer Training": "Training",
	"Demo Garden Visit": "Farm Visit",
	"Payment Collection": "Follow-up",
	"Exhibition": "Other",
}


def complete_linked_task(plan_item_name, on_date=None):
	"""Mark the Promoter Task generated for a plan item as Completed (if any).

	Called when a plan item is reconciled from the actual visit side, so the
	promoter's task list reflects work already done."""
	if not plan_item_name:
		return
	tasks = frappe.get_all("Promoter Task", filters={
		"activity_plan_item": plan_item_name,
		"status": ["not in", ["Completed", "Cancelled"]],
	}, pluck="name")
	for t in tasks:
		frappe.db.set_value("Promoter Task", t, {
			"status": "Completed",
			"completed_on": on_date or today(),
		})


def _ensure_can_approve():
	"""Server-side authority check: only supervisors may approve/reject plans."""
	if not (set(frappe.get_roles()) & APPROVER_ROLES):
		frappe.throw(
			_("Only a supervisor (Agriculture Manager) can approve or reject activity plans."),
			frappe.PermissionError,
		)


def link_activity_to_plan(log):
	"""Match a Field Activity Log to an approved, not-yet-fulfilled planned activity
	and link the two.

	Matching, in order of preference:
	  1. A planned item for the SAME Farmer in an approved plan covering the visit
	     date — so visiting the planned farmer counts even if it happens on a
	     different day than scheduled ("off the planned" day).
	  2. A planned item of the same activity type on the exact planned date.
	A visit that matches nothing stays off-plan (is_planned = 0). On a match the
	Activity Plan Item is marked Done (with the actual date and log) and the plan
	name is returned; otherwise None.
	"""
	if not (getattr(log, "promoter", None) and getattr(log, "activity_date", None)
			and getattr(log, "activity_type", None)):
		return None
	if log.get("activity_plan"):
		return log.activity_plan

	plans = frappe.get_all("Activity Plan", filters={
		"promoter": log.promoter,
		"status": "Approved",
		"from_date": ["<=", log.activity_date],
		"to_date": [">=", log.activity_date],
	}, pluck="name")
	if not plans:
		return None

	base = {"parent": ["in", plans], "parenttype": "Activity Plan"}
	item = None
	# 1) same farmer, anywhere within the plan window
	if getattr(log, "farmer", None):
		item = _first_open_item(dict(base, activity_type=log.activity_type, farmer=log.farmer))
	# 2) same activity type on the exact planned date
	if not item:
		item = _first_open_item(dict(base, activity_type=log.activity_type,
			planned_date=log.activity_date))
	if not item:
		return None

	frappe.db.set_value("Activity Plan Item", item.name, {
		"execution_status": "Done",
		"actual_date": log.activity_date,
		"field_activity_log": log.name,
	})
	complete_linked_task(item.name, log.activity_date)
	return item.parent


def _first_open_item(filters):
	"""First Activity Plan Item matching filters that is not yet Done."""
	rows = frappe.get_all("Activity Plan Item", filters=filters,
		fields=["name", "parent", "execution_status"], order_by="planned_date asc")
	for r in rows:
		if r.execution_status != "Done":
			return r
	return None

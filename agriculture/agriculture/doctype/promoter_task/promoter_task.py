# Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class PromoterTask(Document):
	def before_insert(self):
		if not self.assigned_by:
			self.assigned_by = frappe.session.user

	def validate(self):
		# Stamp / clear the completion date based on status
		if self.status == "Completed" and not self.completed_on:
			self.completed_on = today()
		if self.status != "Completed":
			self.completed_on = None
		self._sync_plan_item()

	def _sync_plan_item(self):
		"""When a plan-generated task is completed, mark its Activity Plan Item Done
		so the plan-vs-actual view stays in sync (completing the task reconciles
		the plan)."""
		if self.status != "Completed" or not self.activity_plan_item:
			return
		cur = frappe.db.get_value("Activity Plan Item", self.activity_plan_item, "execution_status")
		if cur is not None and cur != "Done":
			frappe.db.set_value("Activity Plan Item", self.activity_plan_item, {
				"execution_status": "Done",
				"actual_date": self.completed_on or today(),
			})

	def after_insert(self):
		# Plan-generated tasks are announced once by the plan, not per task
		if self.flags.get("skip_assignee_notification"):
			return
		self._notify_assignee(
			_("New task assigned: {0}").format(self.subject),
			_("You have been assigned a task: <b>{0}</b> (priority {1}, due {2}).").format(
				self.subject, self.priority, self.due_date or _("not set")),
		)

	def _notify_assignee(self, subject, message):
		"""Notify the assigned promoter (settings-aware: email and/or in-app)."""
		from agriculture.agriculture.tasks import _notify

		email = frappe.db.get_value("Field Promoter", self.promoter, "email_id")
		if email:
			_notify([email], subject, message, "Promoter Task", self.name)

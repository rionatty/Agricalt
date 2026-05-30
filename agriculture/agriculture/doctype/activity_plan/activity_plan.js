// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Activity Plan", {
	refresh(frm) {
		if (frm.is_new()) return;
		const status = frm.doc.status;
		const is_supervisor = frappe.user.has_role(["Agriculture Manager", "System Manager"]);

		if (status === "Draft") {
			frm.add_custom_button(__("Submit for Approval"), () => {
				frm.call("submit_for_approval").then(() => frm.reload_doc());
			}).addClass("btn-primary");
		}

		if (status === "Submitted" && is_supervisor) {
			frm.add_custom_button(__("Approve"), () => {
				frm.call("approve").then(() => frm.reload_doc());
			}, __("Actions")).addClass("btn-primary");

			frm.add_custom_button(__("Reject"), () => {
				frappe.prompt(
					[{ fieldname: "reason", fieldtype: "Small Text", label: __("Rejection Reason"), reqd: 1 }],
					(v) => frm.call("reject", { reason: v.reason }).then(() => frm.reload_doc()),
					__("Reject Activity Plan")
				);
			}, __("Actions"));
		}
	},
});

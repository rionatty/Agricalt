// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Demo Garden Material Request", {
	refresh(frm) {
		if (frm.is_new()) return;
		const status = frm.doc.status;
		const is_supervisor = frappe.user.has_role(["Agriculture Manager", "System Manager"]);
		const is_store = frappe.user.has_role(["Store Manager", "System Manager"]);

		if (status === "Draft") {
			frm.add_custom_button(__("Submit Request"), () => {
				frm.call("submit_request").then(() => frm.reload_doc());
			}).addClass("btn-success agri-btn-main");
		}

		if (status === "Submitted" && is_supervisor) {
			frm.add_custom_button(__("Approve"), () => {
				frm.call("approve_request").then(() => frm.reload_doc());
			}, __("Actions")).addClass("btn-success agri-btn-main");

			frm.add_custom_button(__("Reject"), () => {
				frappe.prompt(
					[{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 }],
					(v) => frm.call("reject_request", { reason: v.reason }).then(() => frm.reload_doc()),
					__("Reject Request")
				);
			}, __("Actions"));
		}

		if (status === "Approved" && is_store) {
			frm.add_custom_button(__("Mark as Issued"), () => {
				frm.call("mark_issued").then(() => frm.reload_doc());
			}).addClass("btn-success agri-btn-main");
		}

		if (status === "Issued") {
			frm.add_custom_button(__("Confirm Receipt"), () => {
				frappe.confirm(__("Confirm you have received all materials? This updates your stock balance."),
					() => frm.call("confirm_receipt").then(() => frm.reload_doc()));
			}).addClass("btn-success agri-btn-main");
		}
	},
});

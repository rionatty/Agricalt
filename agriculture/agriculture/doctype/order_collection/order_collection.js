// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Order Collection", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("Submit Order"), () => {
				frm.call("submit_order").then(() => frm.reload_doc());
			}).addClass("btn-primary");
		}
		if (frm.doc.status !== "Draft" && !frm.doc.erp_synced
			&& frappe.user.has_role(["Agriculture Manager", "System Manager"])) {
			frm.add_custom_button(__("Push to SAP B1"), () => {
				frappe.call({
					method: "agriculture.agriculture.sap_integration.push_order",
					args: { order_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Pushing to SAP B1..."),
				}).then(() => frm.reload_doc());
			}, __("Integration"));
		}
	},
});

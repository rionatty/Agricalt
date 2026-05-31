// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Field Activity Log", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("Submit Activity"), () => {
				frm.call("submit_activity").then(() => frm.reload_doc());
			}).addClass("btn-success agri-btn-main");
		}
	},
});

// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Demo Garden Input Application", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("Submit Application"), () => {
				frm.call("submit_application").then(() => frm.reload_doc());
			}).addClass("btn-success agri-btn-main");
		}
	},
});

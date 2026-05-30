// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Demo Garden Field Day", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status !== "Completed") {
			frm.add_custom_button(__("Mark Complete"), () => {
				frm.call("mark_complete").then(() => frm.reload_doc());
			}).addClass("btn-primary");
		}
	},
});

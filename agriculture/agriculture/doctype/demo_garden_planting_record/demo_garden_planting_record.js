// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Demo Garden Planting Record", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("Submit Planting"), () => {
				frm.call("submit_planting").then(() => frm.reload_doc());
			}).addClass("btn-primary");
		}
	},
});

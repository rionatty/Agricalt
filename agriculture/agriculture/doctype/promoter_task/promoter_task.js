// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Promoter Task", {
	refresh(frm) {
		if (frm.is_new()) return;
		const status = frm.doc.status;
		if (status === "Completed" || status === "Cancelled") return;

		if (status !== "In Progress") {
			frm.add_custom_button(__("Start"), () => {
				frm.set_value("status", "In Progress");
				frm.save();
			}).addClass("agri-btn-main");
		}

		frm.add_custom_button(__("Mark Complete"), () => {
			frm.set_value("status", "Completed");
			frm.save();
		}).addClass("btn-success agri-btn-main");
	},
});

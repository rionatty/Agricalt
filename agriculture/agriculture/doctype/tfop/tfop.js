// Copyright (c) 2026, CyveTech and contributors
// For license information, please see license.txt

frappe.ui.form.on("TFOP", {
	onload(frm) {
		// Default the Sector Specialist to the logged-in user on a new doc.
		if (frm.is_new() && !frm.doc.sector_specialist) {
			frm.set_value("sector_specialist", frappe.session.user);
		}
	},

	refresh(frm) {
		// Quick action: post an actual against an approved campaign.
		if (!frm.is_new() && frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Post Actual"), () => {
				frappe.new_doc("TFOP Actual", { tfop: frm.doc.name });
			});
		}
	},
});

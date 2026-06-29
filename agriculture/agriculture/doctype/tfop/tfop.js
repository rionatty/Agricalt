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
		if (frm.is_new()) return;
		// Post an actual against an approved campaign.
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Post Actual"), () => {
				frappe.route_options = { tfop: frm.doc.name };
				frappe.new_doc("TFOP Actual");
			}, __("Create"));
		}
		// Request the planned marketing materials (-> SAP B1 transfer request).
		if ((frm.doc.marketing_materials || []).length) {
			frm.add_custom_button(__("Request Materials"), () => {
				frappe.route_options = { tfop: frm.doc.name };
				frappe.new_doc("Marketing Material Request");
			}, __("Create"));
		}
		// Request a cash advance for Activities + Other Costs (-> SAP B1 Down Payment Request).
		if (frm.doc.docstatus === 1
			&& ((frm.doc.activities || []).length || (frm.doc.other_costs || []).length)) {
			frm.add_custom_button(__("Cash Requisition"), () => {
				frappe.route_options = { tfop: frm.doc.name };
				frappe.new_doc("Cash Requisition");
			}, __("Create"));
		}
	},
});

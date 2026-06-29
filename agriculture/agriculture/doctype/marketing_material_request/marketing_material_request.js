// Copyright (c) 2026, CyveTech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Marketing Material Request", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.requested_by) {
			frm.set_value("requested_by", frappe.session.user);
		}
		// Launched from a TFOP ("Request Materials" button) — preset the campaign,
		// which fires the tfop handler to load its marketing-material lines.
		if (frm.is_new() && frappe.route_options && frappe.route_options.tfop) {
			frm.set_value("tfop", frappe.route_options.tfop);
			frappe.route_options = null;
		}
	},

	refresh(frm) {
		// Re-post to SAP B1 if it hasn't posted yet (e.g. SAP was down on submit).
		if (frm.doc.docstatus === 1 && frm.doc.sap_status !== "Posted") {
			frm.add_custom_button(__("Resend to SAP B1"), () => {
				frappe.call({
					method: "agriculture.agriculture.sap_integration.push_marketing_material_request",
					args: { request_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Posting to SAP B1…"),
				}).then(() => frm.reload_doc());
			});
		}
	},

	tfop(frm) {
		if (!frm.doc.tfop) return;
		// Only auto-fill when the items table is empty, so we never clobber edits.
		if ((frm.doc.items || []).length) return;
		frappe.db.get_doc("TFOP", frm.doc.tfop).then((tfop) => {
			(tfop.marketing_materials || []).forEach((r) => {
				const row = frm.add_child("items");
				row.item = r.item;
				row.item_name = r.item_name;
				row.qty = r.qty;
				row.uom = r.uom;
			});
			frm.refresh_field("items");
		});
	},
});

frappe.listview_settings["Marketing Material Request"] = {
	get_indicator(doc) {
		const map = { Posted: "green", Pending: "orange", Failed: "red", "Not Posted": "gray" };
		const s = doc.sap_status || "Not Posted";
		return [__(s), map[s] || "gray", "sap_status,=," + s];
	},
};

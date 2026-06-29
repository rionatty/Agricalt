// Copyright (c) 2026, CyveTech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Marketing Material Request", {
	onload(frm) {
		if (frm.is_new()) {
			if (!frm.doc.requested_by) {
				frm.set_value("requested_by", frappe.session.user);
			}
			// Auto-fill from_warehouse from the logged-in user's warehouse assignment.
			if (!frm.doc.from_warehouse) {
				frappe.call({
					method: "agriculture.agriculture.sap_integration.get_user_default_warehouse",
				}).then(r => {
					if (r.message) frm.set_value("from_warehouse", r.message);
				});
			}
			// Launched from a TFOP ("Request Materials" button) — preset the campaign.
			if (frappe.route_options && frappe.route_options.tfop) {
				frm.set_value("tfop", frappe.route_options.tfop);
				frappe.route_options = null;
			}
		}
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;

		// Re-post to SAP B1 if it hasn't posted yet (e.g. SAP was down on submit).
		if (frm.doc.sap_status !== "Posted") {
			frm.add_custom_button(__("Resend to SAP B1"), () => {
				frappe.call({
					method: "agriculture.agriculture.sap_integration.push_marketing_material_request",
					args: { request_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Posting to SAP B1…"),
				}).then(() => frm.reload_doc());
			});
		}

		// Manual receipt sync — shows when posted but not yet received.
		if (frm.doc.sap_status === "Posted" && frm.doc.receipt_status !== "Received") {
			frm.add_custom_button(__("Sync Receipt from SAP"), () => {
				frappe.call({
					method: "agriculture.agriculture.sap_integration.check_mmr_receipt",
					args: { mmr_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Checking SAP B1…"),
				}).then(r => {
					const res = r.message || {};
					if (res.status === "received") {
						frappe.show_alert({ message: __("Materials received — Stock Entry created."), indicator: "green" });
						frm.reload_doc();
					} else if (res.status === "still_open") {
						frappe.show_alert({ message: __("SAP Transfer Request is still open — goods not yet issued."), indicator: "orange" });
					} else if (res.status === "already_received") {
						frappe.show_alert({ message: __("Already received."), indicator: "blue" });
					} else {
						frappe.show_alert({ message: res.message || __("Could not check SAP status."), indicator: "red" });
					}
				});
			}, __("SAP B1"));
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
		if (doc.receipt_status === "Received") {
			return [__("Received"), "green", "receipt_status,=,Received"];
		}
		const map = { Posted: "blue", Pending: "orange", Failed: "red", "Not Posted": "gray" };
		const s = doc.sap_status || "Not Posted";
		return [__(s), map[s] || "gray", "sap_status,=," + s];
	},
};

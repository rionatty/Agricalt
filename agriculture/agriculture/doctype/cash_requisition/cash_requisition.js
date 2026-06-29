// Copyright (c) 2026, CyveTech and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cash Requisition", {
	onload(frm) {
		if (frm.is_new()) {
			if (!frm.doc.requested_by) {
				frm.set_value("requested_by", frappe.session.user);
			}
			// Launched from a TFOP ("Cash Requisition" button) — preset the campaign,
			// which fires the tfop handler to load its Activity + Other Cost lines.
			if (frappe.route_options && frappe.route_options.tfop) {
				frm.set_value("tfop", frappe.route_options.tfop);
				frappe.route_options = null;
			}
		}
	},

	tfop(frm) {
		if (!frm.doc.tfop) return;
		// Only auto-fill when the items table is empty, so we never clobber edits.
		if ((frm.doc.items || []).length) return;
		frappe.db.get_doc("TFOP", frm.doc.tfop).then((tfop) => {
			(tfop.activities || []).forEach((r) => {
				if (!flt(r.amount)) return;
				const row = frm.add_child("items");
				row.source = "Activity";
				row.description = r.activity;
				row.amount = r.amount;
			});
			(tfop.other_costs || []).forEach((r) => {
				if (!flt(r.amount)) return;
				const row = frm.add_child("items");
				row.source = "Other Cost";
				row.description = r.cost_description;
				row.amount = r.amount;
			});
			frm.refresh_field("items");
			frm.trigger("recalc_total");
		});
	},

	recalc_total(frm) {
		const total = (frm.doc.items || []).reduce((s, r) => s + flt(r.amount), 0);
		frm.set_value("total_amount", total);
	},

	refresh(frm) {
		// Re-post to SAP B1 if it hasn't posted yet (e.g. SAP was down on submit).
		if (frm.doc.docstatus === 1 && frm.doc.sap_status !== "Posted") {
			frm.add_custom_button(__("Resend to SAP B1"), () => {
				frappe.call({
					method: "agriculture.agriculture.sap_integration.push_cash_requisition",
					args: { requisition_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Posting to SAP B1…"),
				}).then(() => frm.reload_doc());
			});
		}
	},
});

frappe.ui.form.on("Cash Requisition Item", {
	amount(frm) {
		frm.trigger("recalc_total");
	},
	items_remove(frm) {
		frm.trigger("recalc_total");
	},
});

frappe.listview_settings["Cash Requisition"] = {
	get_indicator(doc) {
		const map = { Posted: "green", Pending: "orange", Failed: "red", "Not Posted": "gray" };
		const s = doc.sap_status || "Not Posted";
		return [__(s), map[s] || "gray", "sap_status,=," + s];
	},
};

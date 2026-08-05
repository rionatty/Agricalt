// Copyright (c) 2026, Frappe Technologies, AgriTheory and contributors
// For license information, please see license.txt

frappe.ui.form.on("Material Receipt", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("Submit Receipt"), () => {
				frm.call("submit_receipt").then(() => frm.reload_doc());
			}).addClass("btn-success");
		}
	},
	material_request(frm) {
		// When a Material Request is selected, fetch its items into this
		// receipt — saves the user from re-typing.
		if (!frm.doc.material_request) return;
		frappe.db.get_doc("Demo Garden Material Request", frm.doc.material_request).then((mr) => {
			frm.set_value("promoter", mr.promoter);
			frm.set_value("demo_garden", mr.demo_garden);
			frm.set_value("issued_by", mr.issued_by || "");
			frm.set_value("issue_date", mr.issue_date || "");
			frm.clear_table("items");
			(mr.items || []).forEach((it) => {
				const child = frm.add_child("items");
				child.item_type = it.item_type;
				child.item = it.item;
				child.item_name = it.item_name;
				child.uom = it.uom;
				child.quantity_received = it.quantity_issued || it.quantity_received || it.quantity_requested;
			});
			frm.refresh_field("items");
		});
	},
});
